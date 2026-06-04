package postgres

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"icore-payment-service/internal/domain/catalog"
	"icore-payment-service/internal/domain/payment"

	"github.com/google/uuid"
	_ "github.com/jackc/pgx/v5/stdlib"
)

const orderColumns = `
  id,
  out_trade_no,
  user_public_id,
  plan_code,
  billing_period,
  amount_cents,
  currency,
  status,
  code_url,
  code_url_expires_at,
  wechat_transaction_id,
  wechat_trade_state,
  client_request_id,
  idempotency_key,
  version,
  created_at,
  updated_at,
  paid_at,
  closed_at
`

// DBConfig configures the payment-service PostgreSQL connection pool.
type DBConfig struct {
	DatabaseURL        string
	MaxOpenConns       int
	MaxIdleConns       int
	ConnMaxLifetime    time.Duration
	InitialPingTimeout time.Duration
}

// Repository persists payment orders, provider audit events, and outbox records.
type Repository struct {
	db      *sql.DB
	catalog catalog.Catalog
	now     func() time.Time
}

// OutboxMessage is a pending Kafka event claimed from the transactional outbox.
type OutboxMessage struct {
	ID           string
	EventType    string
	PartitionKey string
	Payload      []byte
	CreatedAt    time.Time
}

// Open opens and verifies a PostgreSQL connection using the pgx database/sql driver.
func Open(ctx context.Context, config DBConfig) (*sql.DB, error) {
	if config.DatabaseURL == "" {
		return nil, fmt.Errorf("PAYMENT_DATABASE_URL is required")
	}
	db, err := sql.Open("pgx", config.DatabaseURL)
	if err != nil {
		return nil, err
	}
	if config.MaxOpenConns > 0 {
		db.SetMaxOpenConns(config.MaxOpenConns)
	}
	if config.MaxIdleConns > 0 {
		db.SetMaxIdleConns(config.MaxIdleConns)
	}
	if config.ConnMaxLifetime > 0 {
		db.SetConnMaxLifetime(config.ConnMaxLifetime)
	}
	pingTimeout := config.InitialPingTimeout
	if pingTimeout <= 0 {
		pingTimeout = 5 * time.Second
	}
	pingCtx, cancel := context.WithTimeout(ctx, pingTimeout)
	defer cancel()
	if err := db.PingContext(pingCtx); err != nil {
		_ = db.Close()
		return nil, err
	}
	return db, nil
}

// NewRepository creates a payment PostgreSQL repository.
func NewRepository(db *sql.DB, cat catalog.Catalog, now func() time.Time) *Repository {
	if now == nil {
		now = time.Now
	}
	return &Repository{db: db, catalog: cat, now: now}
}

// Check verifies that PostgreSQL is reachable.
func (repo *Repository) Check(ctx context.Context) error {
	if repo == nil || repo.db == nil {
		return fmt.Errorf("payment repository is not initialized")
	}
	return repo.db.PingContext(ctx)
}

// FindByIdempotencyKey returns one order by the prepay idempotency key.
func (repo *Repository) FindByIdempotencyKey(ctx context.Context, key string) (payment.Order, error) {
	row := repo.db.QueryRowContext(ctx, "SELECT "+orderColumns+" FROM payment_orders WHERE idempotency_key = $1", key)
	return scanOrder(row)
}

// FindByOutTradeNo returns one order by merchant order number.
func (repo *Repository) FindByOutTradeNo(ctx context.Context, outTradeNo string) (payment.Order, error) {
	row := repo.db.QueryRowContext(ctx, "SELECT "+orderColumns+" FROM payment_orders WHERE out_trade_no = $1", outTradeNo)
	return scanOrder(row)
}

// FindByOutTradeNoForUser returns one user-scoped order by merchant order number.
func (repo *Repository) FindByOutTradeNoForUser(ctx context.Context, outTradeNo string, userID string) (payment.Order, error) {
	row := repo.db.QueryRowContext(ctx, "SELECT "+orderColumns+" FROM payment_orders WHERE out_trade_no = $1 AND user_public_id = $2", outTradeNo, userID)
	return scanOrder(row)
}

// CreateOrder inserts a new local payment order.
func (repo *Repository) CreateOrder(ctx context.Context, order payment.Order) error {
	_, err := repo.db.ExecContext(ctx, `
INSERT INTO payment_orders (
  id, out_trade_no, user_public_id, plan_code, billing_period, amount_cents,
  currency, status, client_request_id, idempotency_key, version, created_at, updated_at
) VALUES (
  $1, $2, $3, $4, $5, $6,
  $7, $8, $9, $10, $11, $12, $13
)`,
		order.ID,
		order.OutTradeNo,
		order.UserPublicID,
		order.PlanCode,
		order.BillingPeriod,
		order.AmountCents,
		order.Currency,
		string(order.Status),
		order.ClientRequestID,
		order.IdempotencyKey,
		order.Version,
		order.CreatedAt,
		order.UpdatedAt,
	)
	return err
}

// MarkPending stores the provider code_url after a successful Native prepay call.
func (repo *Repository) MarkPending(ctx context.Context, outTradeNo string, codeURL string, expiresAt time.Time) (payment.Order, error) {
	row := repo.db.QueryRowContext(ctx, `
UPDATE payment_orders
SET status = 'pending',
    code_url = $2,
    code_url_expires_at = $3,
    version = version + 1,
    updated_at = now()
WHERE out_trade_no = $1
RETURNING `+orderColumns,
		outTradeNo,
		codeURL,
		expiresAt,
	)
	return scanOrder(row)
}

// MarkClosed marks a user-owned unpaid order as closed.
func (repo *Repository) MarkClosed(ctx context.Context, outTradeNo string, userID string, closedAt time.Time) (payment.Order, error) {
	row := repo.db.QueryRowContext(ctx, `
UPDATE payment_orders
SET status = 'closed',
    closed_at = $3,
    version = version + 1,
    updated_at = now()
WHERE out_trade_no = $1
  AND user_public_id = $2
  AND status <> 'paid'
RETURNING `+orderColumns,
		outTradeNo,
		userID,
		closedAt,
	)
	return scanOrder(row)
}

// MarkPaidByProvider applies a verified provider success notification and writes the success outbox event.
func (repo *Repository) MarkPaidByProvider(ctx context.Context, notification payment.ProviderNotification) (payment.Order, error) {
	tx, err := repo.db.BeginTx(ctx, &sql.TxOptions{})
	if err != nil {
		return payment.Order{}, err
	}
	defer rollbackUnlessCommitted(tx)

	order, err := repo.findByOutTradeNoForUpdate(ctx, tx, notification.Transaction.OutTradeNo)
	if err != nil {
		return payment.Order{}, err
	}
	if err := verifyProviderTransaction(order, notification.Transaction); err != nil {
		return payment.Order{}, err
	}
	if err := repo.insertOrderEvent(ctx, tx, order, notification); err != nil {
		return payment.Order{}, err
	}
	if order.Status == payment.StatusPaid {
		if err := tx.Commit(); err != nil {
			return payment.Order{}, err
		}
		return order, nil
	}

	paidAt := repo.now().UTC()
	if notification.Transaction.SuccessTime != nil {
		paidAt = notification.Transaction.SuccessTime.UTC()
	}
	updated, err := updatePaidOrder(ctx, tx, order.OutTradeNo, notification.Transaction, paidAt)
	if err != nil {
		return payment.Order{}, err
	}
	if err := repo.insertSucceededOutbox(ctx, tx, updated); err != nil {
		return payment.Order{}, err
	}
	if err := tx.Commit(); err != nil {
		return payment.Order{}, err
	}
	return updated, nil
}

// ClaimPendingOutbox claims pending outbox messages for publishing.
func (repo *Repository) ClaimPendingOutbox(ctx context.Context, limit int) ([]OutboxMessage, error) {
	if limit <= 0 {
		limit = 50
	}
	rows, err := repo.db.QueryContext(ctx, `
UPDATE payment_outbox
SET status = 'publishing',
    attempts = attempts + 1,
    next_attempt_at = now() + interval '30 seconds'
WHERE id IN (
  SELECT id
  FROM payment_outbox
  WHERE status = 'pending'
    AND next_attempt_at <= now()
  ORDER BY created_at
  LIMIT $1
  FOR UPDATE SKIP LOCKED
)
RETURNING id, event_type, partition_key, payload, created_at`,
		limit,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	messages := []OutboxMessage{}
	for rows.Next() {
		var message OutboxMessage
		if err := rows.Scan(&message.ID, &message.EventType, &message.PartitionKey, &message.Payload, &message.CreatedAt); err != nil {
			return nil, err
		}
		messages = append(messages, message)
	}
	return messages, rows.Err()
}

// MarkOutboxPublished records that an outbox message was accepted by Kafka.
func (repo *Repository) MarkOutboxPublished(ctx context.Context, id string) error {
	_, err := repo.db.ExecContext(ctx, `
UPDATE payment_outbox
SET status = 'published',
    published_at = now(),
    last_error = NULL
WHERE id = $1`,
		id,
	)
	return err
}

// MarkOutboxFailed returns an outbox message to pending retry state.
func (repo *Repository) MarkOutboxFailed(ctx context.Context, id string, publishErr error) error {
	message := ""
	if publishErr != nil {
		message = publishErr.Error()
	}
	_, err := repo.db.ExecContext(ctx, `
UPDATE payment_outbox
SET status = 'pending',
    next_attempt_at = now() + interval '30 seconds',
    last_error = $2
WHERE id = $1`,
		id,
		message,
	)
	return err
}

func (repo *Repository) findByOutTradeNoForUpdate(ctx context.Context, tx *sql.Tx, outTradeNo string) (payment.Order, error) {
	row := tx.QueryRowContext(ctx, "SELECT "+orderColumns+" FROM payment_orders WHERE out_trade_no = $1 FOR UPDATE", outTradeNo)
	return scanOrder(row)
}

func (repo *Repository) insertOrderEvent(ctx context.Context, tx *sql.Tx, order payment.Order, notification payment.ProviderNotification) error {
	payload := notification.RawPayload
	if len(payload) == 0 {
		payload = []byte(`{}`)
	}
	_, err := tx.ExecContext(ctx, `
INSERT INTO payment_order_events (
  id, order_id, event_type, local_status, provider, provider_event_id,
  provider_trade_state, payload
) VALUES (
  $1, $2, $3, $4, 'wechatpay', $5,
  $6, $7
)
ON CONFLICT DO NOTHING`,
		uuid.NewString(),
		order.ID,
		notification.EventType,
		string(order.Status),
		notification.EventID,
		notification.Transaction.TradeState,
		json.RawMessage(payload),
	)
	return err
}

func (repo *Repository) insertSucceededOutbox(ctx context.Context, tx *sql.Tx, order payment.Order) error {
	item, ok := repo.catalog.Find(order.PlanCode, order.BillingPeriod)
	if !ok {
		return fmt.Errorf("payment catalog missing %s %s for succeeded outbox", order.PlanCode, order.BillingPeriod)
	}
	eventID := uuid.NewString()
	payload, err := json.Marshal(map[string]any{
		"event_id":              eventID,
		"event_type":            "payment.order.succeeded",
		"occurred_at":           repo.now().UTC().Format(time.RFC3339Nano),
		"order_id":              order.ID,
		"out_trade_no":          order.OutTradeNo,
		"wechat_transaction_id": order.WechatTransactionID,
		"user_id":               order.UserPublicID,
		"plan_code":             order.PlanCode,
		"billing_period":        order.BillingPeriod,
		"amount": map[string]any{
			"currency": order.Currency,
			"total":    order.AmountCents,
		},
		"entitlements_version": item.EntitlementsVersion,
	})
	if err != nil {
		return err
	}
	_, err = tx.ExecContext(ctx, `
INSERT INTO payment_outbox (
  id, aggregate_type, aggregate_id, event_type, partition_key, payload
) VALUES (
  $1, 'payment_order', $2, 'payment.order.succeeded', $3, $4
)`,
		eventID,
		order.ID,
		order.UserPublicID,
		json.RawMessage(payload),
	)
	return err
}

func updatePaidOrder(ctx context.Context, tx *sql.Tx, outTradeNo string, transaction payment.ProviderTransaction, paidAt time.Time) (payment.Order, error) {
	row := tx.QueryRowContext(ctx, `
UPDATE payment_orders
SET status = 'paid',
    wechat_transaction_id = $2,
    wechat_trade_state = $3,
    paid_at = $4,
    version = version + 1,
    updated_at = now()
WHERE out_trade_no = $1
RETURNING `+orderColumns,
		outTradeNo,
		transaction.TransactionID,
		transaction.TradeState,
		paidAt,
	)
	return scanOrder(row)
}

func verifyProviderTransaction(order payment.Order, transaction payment.ProviderTransaction) error {
	if transaction.OutTradeNo != order.OutTradeNo {
		return payment.ErrProviderMismatch
	}
	if transaction.AmountCents != order.AmountCents || transaction.Currency != order.Currency {
		return payment.ErrProviderMismatch
	}
	if transaction.TransactionID == "" || transaction.TradeState != "SUCCESS" {
		return payment.ErrProviderMismatch
	}
	return nil
}

type rowScanner interface {
	Scan(dest ...any) error
}

func scanOrder(scanner rowScanner) (payment.Order, error) {
	var order payment.Order
	var status string
	var codeURL sql.NullString
	var codeURLExpiresAt sql.NullTime
	var wechatTransactionID sql.NullString
	var wechatTradeState sql.NullString
	var paidAt sql.NullTime
	var closedAt sql.NullTime
	err := scanner.Scan(
		&order.ID,
		&order.OutTradeNo,
		&order.UserPublicID,
		&order.PlanCode,
		&order.BillingPeriod,
		&order.AmountCents,
		&order.Currency,
		&status,
		&codeURL,
		&codeURLExpiresAt,
		&wechatTransactionID,
		&wechatTradeState,
		&order.ClientRequestID,
		&order.IdempotencyKey,
		&order.Version,
		&order.CreatedAt,
		&order.UpdatedAt,
		&paidAt,
		&closedAt,
	)
	if errors.Is(err, sql.ErrNoRows) {
		return payment.Order{}, payment.ErrOrderNotFound
	}
	if err != nil {
		return payment.Order{}, err
	}
	order.Status = payment.Status(status)
	order.CodeURL = codeURL.String
	if codeURLExpiresAt.Valid {
		order.CodeURLExpiresAt = &codeURLExpiresAt.Time
	}
	order.WechatTransactionID = wechatTransactionID.String
	order.WechatTradeState = wechatTradeState.String
	if paidAt.Valid {
		order.PaidAt = &paidAt.Time
	}
	if closedAt.Valid {
		order.ClosedAt = &closedAt.Time
	}
	return order, nil
}

func rollbackUnlessCommitted(tx *sql.Tx) {
	_ = tx.Rollback()
}
