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

const orderBaseColumns = `
  o.id,
  o.order_no,
  o.user_public_id,
  o.plan_code,
  o.billing_period,
  o.amount_cents,
  o.currency,
  o.status,
  o.client_request_id,
  o.idempotency_key,
  o.version,
  o.created_at,
  o.updated_at,
  o.paid_at,
  o.closed_at
`

const providerTransactionColumns = `
  pt.id,
  pt.order_id,
  pt.provider,
  pt.payment_method,
  pt.merchant_id,
  pt.merchant_order_no,
  pt.provider_transaction_id,
  pt.provider_trade_state,
  pt.status,
  pt.payment_payload,
  pt.expires_at,
  pt.created_at,
  pt.updated_at,
  pt.paid_at,
  pt.closed_at
`

const providerTransactionReturnColumns = `
  id,
  order_id,
  provider,
  payment_method,
  merchant_id,
  merchant_order_no,
  provider_transaction_id,
  provider_trade_state,
  status,
  payment_payload,
  expires_at,
  created_at,
  updated_at,
  paid_at,
  closed_at
`

const orderWithLatestProviderTransactionQuery = `
SELECT ` + orderBaseColumns + `,
       ` + providerTransactionColumns + `
FROM payment_orders o
LEFT JOIN LATERAL (
  SELECT *
  FROM payment_provider_transactions
  WHERE order_id = o.id
  ORDER BY created_at DESC
  LIMIT 1
) pt ON true
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
	row := repo.db.QueryRowContext(ctx, orderWithLatestProviderTransactionQuery+" WHERE o.idempotency_key = $1", key)
	return scanOrderWithProviderTransaction(row)
}

// FindByOrderNo returns one order by local merchant order number.
func (repo *Repository) FindByOrderNo(ctx context.Context, orderNo string) (payment.Order, error) {
	row := repo.db.QueryRowContext(ctx, orderWithLatestProviderTransactionQuery+" WHERE o.order_no = $1", orderNo)
	return scanOrderWithProviderTransaction(row)
}

// FindByOrderNoForUser returns one user-scoped order by local merchant order number.
func (repo *Repository) FindByOrderNoForUser(ctx context.Context, orderNo string, userID string) (payment.Order, error) {
	row := repo.db.QueryRowContext(ctx, orderWithLatestProviderTransactionQuery+" WHERE o.order_no = $1 AND o.user_public_id = $2", orderNo, userID)
	return scanOrderWithProviderTransaction(row)
}

// CreateOrder inserts a new local payment order.
func (repo *Repository) CreateOrder(ctx context.Context, order payment.Order) error {
	_, err := repo.db.ExecContext(ctx, `
INSERT INTO payment_orders (
  id, order_no, user_public_id, plan_code, billing_period, amount_cents,
  currency, status, client_request_id, idempotency_key, version, created_at, updated_at
) VALUES (
  $1, $2, $3, $4, $5, $6,
  $7, $8, $9, $10, $11, $12, $13
)`,
		order.ID,
		order.OrderNo,
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

// MarkProviderPending stores a successful provider prepay transaction and marks the local order pending.
func (repo *Repository) MarkProviderPending(ctx context.Context, orderNo string, transaction payment.ProviderTransactionRecord) (payment.Order, error) {
	tx, err := repo.db.BeginTx(ctx, &sql.TxOptions{})
	if err != nil {
		return payment.Order{}, err
	}
	defer rollbackUnlessCommitted(tx)

	order, err := updateOrderStatus(ctx, tx, orderNo, payment.StatusPending, nil)
	if err != nil {
		return payment.Order{}, err
	}
	transaction.OrderID = order.ID
	providerTransaction, err := upsertProviderTransaction(ctx, tx, transaction)
	if err != nil {
		return payment.Order{}, err
	}
	if err := tx.Commit(); err != nil {
		return payment.Order{}, err
	}
	order.ProviderTransaction = &providerTransaction
	return order, nil
}

// MarkClosed marks a user-owned unpaid order and its latest provider transaction as closed.
func (repo *Repository) MarkClosed(ctx context.Context, orderNo string, userID string, closedAt time.Time) (payment.Order, error) {
	tx, err := repo.db.BeginTx(ctx, &sql.TxOptions{})
	if err != nil {
		return payment.Order{}, err
	}
	defer rollbackUnlessCommitted(tx)

	row := tx.QueryRowContext(ctx, `
UPDATE payment_orders o
SET status = 'closed',
    closed_at = $3,
    version = version + 1,
    updated_at = now()
WHERE o.order_no = $1
  AND o.user_public_id = $2
  AND o.status <> 'paid'
RETURNING `+orderBaseColumns,
		orderNo,
		userID,
		closedAt,
	)
	order, err := scanOrderBase(row)
	if err != nil {
		return payment.Order{}, err
	}
	providerTransaction, err := closeProviderTransaction(ctx, tx, order.ID, closedAt)
	if err != nil {
		return payment.Order{}, err
	}
	if err := tx.Commit(); err != nil {
		return payment.Order{}, err
	}
	order.ProviderTransaction = providerTransaction
	return order, nil
}

// MarkPaidByProvider applies a verified provider success notification and writes the success outbox event.
func (repo *Repository) MarkPaidByProvider(ctx context.Context, notification payment.ProviderNotification) (payment.Order, error) {
	tx, err := repo.db.BeginTx(ctx, &sql.TxOptions{})
	if err != nil {
		return payment.Order{}, err
	}
	defer rollbackUnlessCommitted(tx)

	order, err := repo.findByOrderNoForUpdate(ctx, tx, notification.Transaction.MerchantOrderNo)
	if err != nil {
		return payment.Order{}, err
	}
	if err := verifyProviderTransaction(order, notification.Transaction); err != nil {
		return payment.Order{}, err
	}
	providerTransaction, err := repo.findProviderTransactionForUpdate(ctx, tx, notification.Transaction)
	if err != nil {
		return payment.Order{}, err
	}
	if err := repo.insertOrderEvent(ctx, tx, order, providerTransaction, notification); err != nil {
		return payment.Order{}, err
	}
	if order.Status == payment.StatusPaid {
		order.ProviderTransaction = &providerTransaction
		if err := tx.Commit(); err != nil {
			return payment.Order{}, err
		}
		return order, nil
	}

	paidAt := repo.now().UTC()
	if notification.Transaction.SuccessTime != nil {
		paidAt = notification.Transaction.SuccessTime.UTC()
	}
	updated, err := updatePaidOrder(ctx, tx, order.OrderNo, paidAt)
	if err != nil {
		return payment.Order{}, err
	}
	updatedProviderTransaction, err := updateProviderTransactionPaid(ctx, tx, providerTransaction, notification.Transaction, paidAt)
	if err != nil {
		return payment.Order{}, err
	}
	updated.ProviderTransaction = &updatedProviderTransaction
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
  WHERE (
    status = 'pending'
    AND next_attempt_at <= now()
  ) OR (
    status = 'publishing'
    AND next_attempt_at <= now()
  )
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

func (repo *Repository) findByOrderNoForUpdate(ctx context.Context, tx *sql.Tx, orderNo string) (payment.Order, error) {
	row := tx.QueryRowContext(ctx, `
SELECT `+orderBaseColumns+`
FROM payment_orders o
WHERE o.order_no = $1
FOR UPDATE`,
		orderNo,
	)
	return scanOrderBase(row)
}

func (repo *Repository) findProviderTransactionForUpdate(ctx context.Context, tx *sql.Tx, transaction payment.ProviderTransaction) (payment.ProviderTransactionRecord, error) {
	row := tx.QueryRowContext(ctx, `
SELECT `+providerTransactionColumns+`
FROM payment_provider_transactions pt
WHERE pt.provider = $1
  AND pt.merchant_id = $2
  AND pt.merchant_order_no = $3
FOR UPDATE`,
		transaction.Provider,
		transaction.MerchantID,
		transaction.MerchantOrderNo,
	)
	return scanProviderTransaction(row)
}

func (repo *Repository) insertOrderEvent(ctx context.Context, tx *sql.Tx, order payment.Order, providerTransaction payment.ProviderTransactionRecord, notification payment.ProviderNotification) error {
	payload := notification.RawPayload
	if len(payload) == 0 {
		payload = []byte(`{}`)
	}
	_, err := tx.ExecContext(ctx, `
INSERT INTO payment_order_events (
  id, order_id, payment_provider_transaction_id, event_type, local_status,
  provider, merchant_id, merchant_order_no, provider_event_id,
  provider_transaction_id, provider_trade_state, payload
) VALUES (
  $1, $2, $3, $4, $5,
  $6, $7, $8, $9,
  $10, $11, $12
)
ON CONFLICT DO NOTHING`,
		uuid.NewString(),
		order.ID,
		providerTransaction.ID,
		notification.EventType,
		string(order.Status),
		notification.Transaction.Provider,
		notification.Transaction.MerchantID,
		notification.Transaction.MerchantOrderNo,
		notification.EventID,
		notification.Transaction.ProviderTransactionID,
		notification.Transaction.ProviderTradeState,
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
	providerPayload := map[string]any{}
	if order.ProviderTransaction != nil {
		providerPayload = map[string]any{
			"name":              order.ProviderTransaction.Provider,
			"method":            order.ProviderTransaction.PaymentMethod,
			"merchant_id":       order.ProviderTransaction.MerchantID,
			"merchant_order_no": order.ProviderTransaction.MerchantOrderNo,
			"transaction_id":    order.ProviderTransaction.ProviderTransactionID,
			"trade_state":       order.ProviderTransaction.ProviderTradeState,
		}
	}
	payload, err := json.Marshal(map[string]any{
		"event_id":       eventID,
		"event_type":     "payment.order.succeeded",
		"occurred_at":    repo.now().UTC().Format(time.RFC3339Nano),
		"order_id":       order.ID,
		"order_no":       order.OrderNo,
		"user_id":        order.UserPublicID,
		"plan_code":      order.PlanCode,
		"billing_period": order.BillingPeriod,
		"amount": map[string]any{
			"currency": order.Currency,
			"total":    order.AmountCents,
		},
		"provider":             providerPayload,
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

func updateOrderStatus(ctx context.Context, tx *sql.Tx, orderNo string, status payment.Status, paidAt *time.Time) (payment.Order, error) {
	row := tx.QueryRowContext(ctx, `
UPDATE payment_orders o
SET status = $2,
    paid_at = COALESCE($3, paid_at),
    version = version + 1,
    updated_at = now()
WHERE o.order_no = $1
RETURNING `+orderBaseColumns,
		orderNo,
		string(status),
		paidAt,
	)
	return scanOrderBase(row)
}

func updatePaidOrder(ctx context.Context, tx *sql.Tx, orderNo string, paidAt time.Time) (payment.Order, error) {
	return updateOrderStatus(ctx, tx, orderNo, payment.StatusPaid, &paidAt)
}

func upsertProviderTransaction(ctx context.Context, tx *sql.Tx, transaction payment.ProviderTransactionRecord) (payment.ProviderTransactionRecord, error) {
	payload, err := json.Marshal(transaction.PaymentPayload)
	if err != nil {
		return payment.ProviderTransactionRecord{}, err
	}
	row := tx.QueryRowContext(ctx, `
INSERT INTO payment_provider_transactions (
  id, order_id, provider, payment_method, merchant_id, merchant_order_no,
  provider_transaction_id, provider_trade_state, status, payment_payload,
  expires_at, created_at, updated_at, paid_at, closed_at
) VALUES (
  $1, $2, $3, $4, $5, $6,
  $7, $8, $9, $10,
  $11, $12, $13, $14, $15
)
ON CONFLICT (provider, merchant_id, merchant_order_no) DO UPDATE
SET payment_method = EXCLUDED.payment_method,
    provider_transaction_id = COALESCE(EXCLUDED.provider_transaction_id, payment_provider_transactions.provider_transaction_id),
    provider_trade_state = COALESCE(EXCLUDED.provider_trade_state, payment_provider_transactions.provider_trade_state),
    status = EXCLUDED.status,
    payment_payload = EXCLUDED.payment_payload,
    expires_at = EXCLUDED.expires_at,
    updated_at = now()
RETURNING `+providerTransactionReturnColumns,
		transaction.ID,
		transaction.OrderID,
		transaction.Provider,
		transaction.PaymentMethod,
		transaction.MerchantID,
		transaction.MerchantOrderNo,
		nullableString(transaction.ProviderTransactionID),
		nullableString(transaction.ProviderTradeState),
		string(transaction.Status),
		json.RawMessage(payload),
		transaction.ExpiresAt,
		transaction.CreatedAt,
		transaction.UpdatedAt,
		transaction.PaidAt,
		transaction.ClosedAt,
	)
	return scanProviderTransaction(row)
}

func updateProviderTransactionPaid(ctx context.Context, tx *sql.Tx, providerTransaction payment.ProviderTransactionRecord, transaction payment.ProviderTransaction, paidAt time.Time) (payment.ProviderTransactionRecord, error) {
	row := tx.QueryRowContext(ctx, `
UPDATE payment_provider_transactions pt
SET status = 'paid',
    provider_transaction_id = $2,
    provider_trade_state = $3,
    paid_at = $4,
    updated_at = now()
WHERE pt.id = $1
RETURNING `+providerTransactionColumns,
		providerTransaction.ID,
		transaction.ProviderTransactionID,
		transaction.ProviderTradeState,
		paidAt,
	)
	return scanProviderTransaction(row)
}

func closeProviderTransaction(ctx context.Context, tx *sql.Tx, orderID string, closedAt time.Time) (*payment.ProviderTransactionRecord, error) {
	row := tx.QueryRowContext(ctx, `
UPDATE payment_provider_transactions pt
SET status = 'closed',
    closed_at = $2,
    updated_at = now()
WHERE pt.id = (
  SELECT id
  FROM payment_provider_transactions
  WHERE order_id = $1
  ORDER BY created_at DESC
  LIMIT 1
)
RETURNING `+providerTransactionColumns,
		orderID,
		closedAt,
	)
	transaction, err := scanProviderTransaction(row)
	if errors.Is(err, payment.ErrOrderNotFound) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &transaction, nil
}

func verifyProviderTransaction(order payment.Order, transaction payment.ProviderTransaction) error {
	if transaction.MerchantOrderNo != order.OrderNo {
		return payment.ErrProviderMismatch
	}
	if transaction.AmountCents != order.AmountCents || transaction.Currency != order.Currency {
		return payment.ErrProviderMismatch
	}
	if transaction.ProviderTransactionID == "" || transaction.ProviderTradeState != "SUCCESS" {
		return payment.ErrProviderMismatch
	}
	return nil
}

type rowScanner interface {
	Scan(dest ...any) error
}

func scanOrderWithProviderTransaction(scanner rowScanner) (payment.Order, error) {
	order, providerTransaction, err := scanOrderAndProviderTransaction(scanner)
	if err != nil {
		return payment.Order{}, err
	}
	order.ProviderTransaction = providerTransaction
	return order, nil
}

func scanOrderAndProviderTransaction(scanner rowScanner) (payment.Order, *payment.ProviderTransactionRecord, error) {
	var order payment.Order
	var status string
	var paidAt sql.NullTime
	var closedAt sql.NullTime
	var providerTransaction providerTransactionScanTarget
	err := scanner.Scan(
		&order.ID,
		&order.OrderNo,
		&order.UserPublicID,
		&order.PlanCode,
		&order.BillingPeriod,
		&order.AmountCents,
		&order.Currency,
		&status,
		&order.ClientRequestID,
		&order.IdempotencyKey,
		&order.Version,
		&order.CreatedAt,
		&order.UpdatedAt,
		&paidAt,
		&closedAt,
		&providerTransaction.id,
		&providerTransaction.orderID,
		&providerTransaction.provider,
		&providerTransaction.paymentMethod,
		&providerTransaction.merchantID,
		&providerTransaction.merchantOrderNo,
		&providerTransaction.providerTransactionID,
		&providerTransaction.providerTradeState,
		&providerTransaction.status,
		&providerTransaction.paymentPayload,
		&providerTransaction.expiresAt,
		&providerTransaction.createdAt,
		&providerTransaction.updatedAt,
		&providerTransaction.paidAt,
		&providerTransaction.closedAt,
	)
	if errors.Is(err, sql.ErrNoRows) {
		return payment.Order{}, nil, payment.ErrOrderNotFound
	}
	if err != nil {
		return payment.Order{}, nil, err
	}
	order.Status = payment.Status(status)
	if paidAt.Valid {
		order.PaidAt = &paidAt.Time
	}
	if closedAt.Valid {
		order.ClosedAt = &closedAt.Time
	}
	transaction, err := providerTransaction.toRecord()
	if err != nil {
		return payment.Order{}, nil, err
	}
	return order, transaction, nil
}

func scanOrderBase(scanner rowScanner) (payment.Order, error) {
	var order payment.Order
	var status string
	var paidAt sql.NullTime
	var closedAt sql.NullTime
	err := scanner.Scan(
		&order.ID,
		&order.OrderNo,
		&order.UserPublicID,
		&order.PlanCode,
		&order.BillingPeriod,
		&order.AmountCents,
		&order.Currency,
		&status,
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
	if paidAt.Valid {
		order.PaidAt = &paidAt.Time
	}
	if closedAt.Valid {
		order.ClosedAt = &closedAt.Time
	}
	return order, nil
}

func scanProviderTransaction(scanner rowScanner) (payment.ProviderTransactionRecord, error) {
	var target providerTransactionScanTarget
	err := scanner.Scan(
		&target.id,
		&target.orderID,
		&target.provider,
		&target.paymentMethod,
		&target.merchantID,
		&target.merchantOrderNo,
		&target.providerTransactionID,
		&target.providerTradeState,
		&target.status,
		&target.paymentPayload,
		&target.expiresAt,
		&target.createdAt,
		&target.updatedAt,
		&target.paidAt,
		&target.closedAt,
	)
	if errors.Is(err, sql.ErrNoRows) {
		return payment.ProviderTransactionRecord{}, payment.ErrOrderNotFound
	}
	if err != nil {
		return payment.ProviderTransactionRecord{}, err
	}
	record, err := target.toRecord()
	if err != nil {
		return payment.ProviderTransactionRecord{}, err
	}
	if record == nil {
		return payment.ProviderTransactionRecord{}, payment.ErrOrderNotFound
	}
	return *record, nil
}

type providerTransactionScanTarget struct {
	id                    sql.NullString
	orderID               sql.NullString
	provider              sql.NullString
	paymentMethod         sql.NullString
	merchantID            sql.NullString
	merchantOrderNo       sql.NullString
	providerTransactionID sql.NullString
	providerTradeState    sql.NullString
	status                sql.NullString
	paymentPayload        []byte
	expiresAt             sql.NullTime
	createdAt             sql.NullTime
	updatedAt             sql.NullTime
	paidAt                sql.NullTime
	closedAt              sql.NullTime
}

func (target providerTransactionScanTarget) toRecord() (*payment.ProviderTransactionRecord, error) {
	if !target.id.Valid {
		return nil, nil
	}
	payload := map[string]any{}
	if len(target.paymentPayload) > 0 {
		if err := json.Unmarshal(target.paymentPayload, &payload); err != nil {
			return nil, err
		}
	}
	record := &payment.ProviderTransactionRecord{
		ID:                    target.id.String,
		OrderID:               target.orderID.String,
		Provider:              target.provider.String,
		PaymentMethod:         target.paymentMethod.String,
		MerchantID:            target.merchantID.String,
		MerchantOrderNo:       target.merchantOrderNo.String,
		ProviderTransactionID: target.providerTransactionID.String,
		ProviderTradeState:    target.providerTradeState.String,
		Status:                payment.Status(target.status.String),
		PaymentPayload:        payload,
	}
	if target.expiresAt.Valid {
		record.ExpiresAt = &target.expiresAt.Time
	}
	if target.createdAt.Valid {
		record.CreatedAt = target.createdAt.Time
	}
	if target.updatedAt.Valid {
		record.UpdatedAt = target.updatedAt.Time
	}
	if target.paidAt.Valid {
		record.PaidAt = &target.paidAt.Time
	}
	if target.closedAt.Valid {
		record.ClosedAt = &target.closedAt.Time
	}
	return record, nil
}

func nullableString(value string) any {
	if value == "" {
		return nil
	}
	return value
}

func rollbackUnlessCommitted(tx *sql.Tx) {
	_ = tx.Rollback()
}
