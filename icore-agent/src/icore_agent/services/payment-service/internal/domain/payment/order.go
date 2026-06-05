package payment

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"strings"
	"time"
)

// Status names the local payment order lifecycle state.
type Status string

const (
	// StatusCreated means the local order exists before provider prepay completes.
	StatusCreated Status = "created"
	// StatusPending means the provider returned a payable client payload.
	StatusPending Status = "pending"
	// StatusPaid means a verified provider transaction succeeded.
	StatusPaid Status = "paid"
	// StatusClosed means the unpaid order has been closed.
	StatusClosed Status = "closed"
	// StatusExpired means the local payable window elapsed.
	StatusExpired Status = "expired"
	// StatusFailed means a non-retryable provider or validation failure happened.
	StatusFailed Status = "failed"
)

var (
	// ErrOrderNotFound indicates that no payment order matched the lookup.
	ErrOrderNotFound = errors.New("payment order not found")
	// ErrIdempotencyConflict indicates that an idempotency key was reused for a different payment request.
	ErrIdempotencyConflict = errors.New("payment idempotency conflict")
	// ErrInvalidOrderState indicates that the requested state transition is not allowed.
	ErrInvalidOrderState = errors.New("invalid payment order state")
	// ErrProviderMismatch indicates that a verified provider message does not match the local order.
	ErrProviderMismatch = errors.New("provider payment details do not match local order")
)

// Order is the payment-service source-of-truth aggregate persisted in PostgreSQL.
type Order struct {
	ID                  string
	OrderNo             string
	UserPublicID        string
	PlanCode            string
	BillingPeriod       string
	AmountCents         int64
	Currency            string
	Status              Status
	ClientRequestID     string
	IdempotencyKey      string
	Version             int64
	CreatedAt           time.Time
	UpdatedAt           time.Time
	PaidAt              *time.Time
	ClosedAt            *time.Time
	ProviderTransaction *ProviderTransactionRecord
}

// ProviderTransactionRecord is a persisted provider-side payment transaction for one local order.
type ProviderTransactionRecord struct {
	ID                    string
	OrderID               string
	Provider              string
	PaymentMethod         string
	MerchantID            string
	MerchantOrderNo       string
	ProviderTransactionID string
	ProviderTradeState    string
	Status                Status
	PaymentPayload        map[string]any
	ExpiresAt             *time.Time
	CreatedAt             time.Time
	UpdatedAt             time.Time
	PaidAt                *time.Time
	ClosedAt              *time.Time
}

// ProviderNotification contains a verified and decrypted WeChat Pay notification.
type ProviderNotification struct {
	EventID     string
	EventType   string
	Transaction ProviderTransaction
	RawPayload  []byte
}

// ProviderTransaction contains provider transaction fields needed for validation and persistence.
type ProviderTransaction struct {
	AppID                 string
	MchID                 string
	Provider              string
	PaymentMethod         string
	MerchantID            string
	MerchantOrderNo       string
	ProviderTransactionID string
	ProviderTradeState    string
	Currency              string
	AmountCents           int64
	SuccessTime           *time.Time
}

// IdempotencyKey derives a deterministic key from user, requested plan, period, and client request id.
func IdempotencyKey(userID string, planCode string, billingPeriod string, clientRequestID string) string {
	parts := []string{
		strings.TrimSpace(userID),
		strings.TrimSpace(planCode),
		strings.TrimSpace(billingPeriod),
		strings.TrimSpace(clientRequestID),
	}
	sum := sha256.Sum256([]byte(strings.Join(parts, "\x00")))
	return hex.EncodeToString(sum[:])
}

// MatchesRequest checks whether an existing order can satisfy a repeated prepay request.
func (order Order) MatchesRequest(userID string, planCode string, billingPeriod string, clientRequestID string, amountCents int64, currency string) bool {
	return order.UserPublicID == strings.TrimSpace(userID) &&
		order.PlanCode == strings.TrimSpace(planCode) &&
		order.BillingPeriod == strings.TrimSpace(billingPeriod) &&
		order.ClientRequestID == strings.TrimSpace(clientRequestID) &&
		order.AmountCents == amountCents &&
		order.Currency == strings.ToUpper(strings.TrimSpace(currency))
}

// ReusableForPrepay reports whether an existing order can be returned for an idempotent prepay call.
func (order Order) ReusableForPrepay() bool {
	return order.Status == StatusCreated ||
		order.Status == StatusPending ||
		order.Status == StatusPaid
}
