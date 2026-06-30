package checkout

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"icore-payment-service/internal/application/paymentlog"
	"icore-payment-service/internal/domain/catalog"
	"icore-payment-service/internal/domain/payment"

	"github.com/google/uuid"
)

// Repository persists payment orders for checkout workflows.
type Repository interface {
	FindByIdempotencyKey(context.Context, string) (payment.Order, error)
	FindByOrderNo(context.Context, string) (payment.Order, error)
	CreateOrder(context.Context, payment.Order) error
	MarkProviderPending(context.Context, string, payment.ProviderTransactionRecord) (payment.Order, error)
	FindByOrderNoForUser(context.Context, string, string) (payment.Order, error)
	MarkClosed(context.Context, string, string, time.Time) (payment.Order, error)
	MarkExpiredByProvider(context.Context, string, time.Time) (payment.Order, error)
}

// Provider creates and closes provider-side payment orders.
type Provider interface {
	PrepayNative(context.Context, ProviderPrepayRequest) (ProviderPrepayResult, error)
	CloseOrder(context.Context, string) error
}

// ServiceConfig wires checkout service dependencies and defaults.
type ServiceConfig struct {
	Catalog    catalog.Catalog
	Repository Repository
	Provider   Provider
	Logger     paymentlog.Logger
	AppID      string
	MchID      string
	NotifyURL  string
	OrderTTL   time.Duration
	Now        func() time.Time
	NewOrderID func() string
	NewOrderNo func(time.Time) (string, error)
}

// Service owns payment checkout use cases.
type Service struct {
	catalog    catalog.Catalog
	repository Repository
	provider   Provider
	logger     paymentlog.Logger
	appID      string
	mchID      string
	notifyURL  string
	orderTTL   time.Duration
	now        func() time.Time
	newOrderID func() string
	newOrderNo func(time.Time) (string, error)
}

// CreateNativePrepayInput is the trusted application request for WeChat Native prepay.
type CreateNativePrepayInput struct {
	UserID          string
	PlanCode        string
	BillingPeriod   string
	ClientRequestID string
	RequestID       string
	PayerClientIP   string
}

// GetOrderInput identifies a user-scoped payment order lookup.
type GetOrderInput struct {
	UserID  string
	OrderNo string
}

// CloseOrderInput identifies a user-scoped order close request.
type CloseOrderInput struct {
	UserID    string
	OrderNo   string
	RequestID string
}

// ProviderPrepayRequest is the provider-neutral WeChat Native prepay request.
type ProviderPrepayRequest struct {
	AppID           string
	MchID           string
	Description     string
	MerchantOrderNo string
	TimeExpire      time.Time
	NotifyURL       string
	AmountCents     int64
	Currency        string
	Attach          string
	PayerClientIP   string
}

// ProviderPrepayResult is the provider adapter response consumed by checkout.
type ProviderPrepayResult struct {
	CodeURL string
}

// Amount is the HTTP-facing payment amount value.
type Amount struct {
	Currency string `json:"currency"`
	Total    int64  `json:"total"`
}

// NativePrepayResult is returned after a local order reaches prepay-created state.
type NativePrepayResult struct {
	OrderID string         `json:"order_id"`
	OrderNo string         `json:"order_no"`
	Status  payment.Status `json:"status"`
	Amount  Amount         `json:"amount"`
	Payment PaymentResult  `json:"payment"`
}

// PaymentResult is the provider-neutral payment payload returned to HTTP clients.
type PaymentResult struct {
	Provider        string         `json:"provider"`
	Method          string         `json:"method"`
	MerchantOrderNo string         `json:"merchant_order_no"`
	Payload         map[string]any `json:"payload"`
	ExpiresAt       *time.Time     `json:"expires_at,omitempty"`
}

// OrderResult is the user-facing representation of one payment order.
type OrderResult struct {
	OrderID       string         `json:"order_id"`
	OrderNo       string         `json:"order_no"`
	Status        payment.Status `json:"status"`
	PlanCode      string         `json:"plan_code"`
	BillingPeriod string         `json:"billing_period"`
	Amount        Amount         `json:"amount"`
	Payment       *PaymentResult `json:"payment,omitempty"`
	PaidAt        *time.Time     `json:"paid_at,omitempty"`
	ClosedAt      *time.Time     `json:"closed_at,omitempty"`
	CreatedAt     time.Time      `json:"created_at"`
}

var (
	// ErrInvalidRequest indicates invalid checkout input.
	ErrInvalidRequest = errors.New("invalid payment request")
	// ErrCatalogItemUnavailable indicates that no enabled payment catalog item matches the request.
	ErrCatalogItemUnavailable = errors.New("payment catalog item unavailable")
)

// NewService creates a checkout application service.
func NewService(config ServiceConfig) *Service {
	orderTTL := config.OrderTTL
	if orderTTL <= 0 {
		orderTTL = 30 * time.Minute
	}
	now := config.Now
	if now == nil {
		now = time.Now
	}
	newOrderID := config.NewOrderID
	if newOrderID == nil {
		newOrderID = func() string { return uuid.NewString() }
	}
	newOrderNo := config.NewOrderNo
	if newOrderNo == nil {
		newOrderNo = defaultOrderNo
	}
	return &Service{
		catalog:    config.Catalog,
		repository: config.Repository,
		provider:   config.Provider,
		logger:     config.Logger,
		appID:      strings.TrimSpace(config.AppID),
		mchID:      strings.TrimSpace(config.MchID),
		notifyURL:  strings.TrimSpace(config.NotifyURL),
		orderTTL:   orderTTL,
		now:        now,
		newOrderID: newOrderID,
		newOrderNo: newOrderNo,
	}
}

// CreateNativePrepay creates or returns an idempotent WeChat Pay Native prepay order.
func (service *Service) CreateNativePrepay(ctx context.Context, input CreateNativePrepayInput) (NativePrepayResult, error) {
	input = normalizePrepayInput(input)
	if input.UserID == "" || input.PlanCode == "" || input.BillingPeriod == "" || input.ClientRequestID == "" {
		return NativePrepayResult{}, ErrInvalidRequest
	}
	item, ok := service.catalog.Find(input.PlanCode, input.BillingPeriod)
	if !ok {
		return NativePrepayResult{}, ErrCatalogItemUnavailable
	}
	key := payment.IdempotencyKey(input.UserID, input.PlanCode, input.BillingPeriod, input.ClientRequestID)
	existing, err := service.repository.FindByIdempotencyKey(ctx, key)
	if err == nil {
		if !existing.MatchesRequest(input.UserID, input.PlanCode, input.BillingPeriod, input.ClientRequestID, item.AmountCents, item.Currency) {
			return NativePrepayResult{}, payment.ErrIdempotencyConflict
		}
		if existing.Status == payment.StatusCreated {
			return service.createProviderPrepay(ctx, existing, item, input)
		}
		if existing.Status == payment.StatusPending && existingPrepayExpired(existing, service.now().UTC()) {
			return service.expireExistingPrepay(ctx, existing, input)
		}
		if existing.ReusableForPrepay() {
			return nativePrepayResultFromOrder(existing), nil
		}
		return NativePrepayResult{}, payment.ErrInvalidOrderState
	}
	if !errors.Is(err, payment.ErrOrderNotFound) {
		return NativePrepayResult{}, err
	}

	now := service.now().UTC()
	orderNo, err := service.newOrderNo(now)
	if err != nil {
		return NativePrepayResult{}, err
	}
	order := payment.Order{
		ID:              service.newOrderID(),
		OrderNo:         orderNo,
		UserPublicID:    input.UserID,
		PlanCode:        input.PlanCode,
		BillingPeriod:   input.BillingPeriod,
		AmountCents:     item.AmountCents,
		Currency:        item.Currency,
		Status:          payment.StatusCreated,
		ClientRequestID: input.ClientRequestID,
		IdempotencyKey:  key,
		Version:         1,
		CreatedAt:       now,
		UpdatedAt:       now,
	}
	if err := service.repository.CreateOrder(ctx, order); err != nil {
		return NativePrepayResult{}, err
	}
	return service.createProviderPrepay(ctx, order, item, input)
}

func (service *Service) expireExistingPrepay(ctx context.Context, order payment.Order, input CreateNativePrepayInput) (NativePrepayResult, error) {
	if service.provider != nil {
		if err := service.provider.CloseOrder(ctx, order.OrderNo); err != nil {
			service.logProviderError(ctx, "payment provider close expired order failed", traceIDForPrepay(input), paymentlog.OperationCloseOrder, order, input, err)
			return NativePrepayResult{}, fmt.Errorf("wechat close expired order: %w", err)
		}
	}
	if _, err := service.repository.MarkExpiredByProvider(ctx, order.OrderNo, service.now().UTC()); err != nil {
		return NativePrepayResult{}, err
	}
	return NativePrepayResult{}, payment.ErrPaymentOrderExpired
}

func (service *Service) createProviderPrepay(ctx context.Context, order payment.Order, item catalog.Item, input CreateNativePrepayInput) (NativePrepayResult, error) {
	expiresAt := service.now().UTC().Add(service.orderTTL)
	providerResult, err := service.provider.PrepayNative(ctx, ProviderPrepayRequest{
		AppID:           service.appID,
		MchID:           service.mchID,
		Description:     item.Description,
		MerchantOrderNo: order.OrderNo,
		TimeExpire:      expiresAt,
		NotifyURL:       service.notifyURL,
		AmountCents:     item.AmountCents,
		Currency:        item.Currency,
		Attach:          item.EntitlementsVersion,
		PayerClientIP:   input.PayerClientIP,
	})
	if err != nil {
		service.logProviderError(ctx, "payment provider prepay failed", traceIDForPrepay(input), paymentlog.OperationNativePrepay, order, input, err)
		return NativePrepayResult{}, fmt.Errorf("wechat native prepay: %w", err)
	}
	pendingOrder, err := service.repository.MarkProviderPending(ctx, order.OrderNo, payment.ProviderTransactionRecord{
		ID:              uuid.NewString(),
		OrderID:         order.ID,
		Provider:        payment.ProviderWeChatPay,
		PaymentMethod:   payment.PaymentMethodNative,
		MerchantID:      service.mchID,
		MerchantOrderNo: order.OrderNo,
		Status:          payment.StatusPending,
		PaymentPayload:  map[string]any{"code_url": providerResult.CodeURL},
		ExpiresAt:       &expiresAt,
		CreatedAt:       service.now().UTC(),
		UpdatedAt:       service.now().UTC(),
	})
	if err != nil {
		return NativePrepayResult{}, err
	}
	return nativePrepayResultFromOrder(pendingOrder), nil
}

// GetOrder returns one user-scoped payment order.
func (service *Service) GetOrder(ctx context.Context, input GetOrderInput) (OrderResult, error) {
	userID := strings.TrimSpace(input.UserID)
	orderNo := strings.TrimSpace(input.OrderNo)
	if userID == "" || orderNo == "" {
		return OrderResult{}, ErrInvalidRequest
	}
	order, err := service.repository.FindByOrderNoForUser(ctx, orderNo, userID)
	if err != nil {
		return OrderResult{}, err
	}
	return orderResultFromOrder(order), nil
}

// CloseOrder closes one user-scoped unpaid payment order.
func (service *Service) CloseOrder(ctx context.Context, input CloseOrderInput) (OrderResult, error) {
	userID := strings.TrimSpace(input.UserID)
	orderNo := strings.TrimSpace(input.OrderNo)
	if userID == "" || orderNo == "" {
		return OrderResult{}, ErrInvalidRequest
	}
	order, err := service.repository.FindByOrderNoForUser(ctx, orderNo, userID)
	if err != nil {
		return OrderResult{}, err
	}
	if order.Status == payment.StatusPaid {
		return OrderResult{}, payment.ErrInvalidOrderState
	}
	if order.Status != payment.StatusClosed && service.provider != nil {
		if err := service.provider.CloseOrder(ctx, orderNo); err != nil {
			service.logProviderError(ctx, "payment provider close order failed", strings.TrimSpace(input.RequestID), paymentlog.OperationCloseOrder, order, CreateNativePrepayInput{
				UserID:          userID,
				PlanCode:        order.PlanCode,
				BillingPeriod:   order.BillingPeriod,
				ClientRequestID: order.ClientRequestID,
			}, err)
			return OrderResult{}, fmt.Errorf("wechat close order: %w", err)
		}
	}
	closed, err := service.repository.MarkClosed(ctx, orderNo, userID, service.now().UTC())
	if err != nil {
		return OrderResult{}, err
	}
	return orderResultFromOrder(closed), nil
}

// logProviderError records provider failures with payment and provider metadata.
func (service *Service) logProviderError(ctx context.Context, message string, traceID string, operation string, order payment.Order, input CreateNativePrepayInput, err error) {
	if service.logger == nil {
		return
	}
	metadata := paymentlog.Metadata(
		operation,
		paymentlog.OrderMetadataFromOrder(order),
		paymentlog.ProviderMetadataFromError(payment.ProviderWeChatPay, service.mchID, providerAPIForOperation(operation), err),
		paymentlog.RequestMetadata{
			ClientRequestID: input.ClientRequestID,
			UserPublicID:    input.UserID,
			PayerClientIP:   input.PayerClientIP,
		},
	)
	_ = service.logger.Error(ctx, message, traceID, metadata)
}

// providerAPIForOperation returns the provider API label for a payment workflow operation.
func providerAPIForOperation(operation string) string {
	switch operation {
	case paymentlog.OperationNativePrepay:
		return "native.prepay"
	case paymentlog.OperationCloseOrder:
		return "native.close_order"
	default:
		return ""
	}
}

// traceIDForPrepay returns the gateway request id when available and falls back to client idempotency id.
func traceIDForPrepay(input CreateNativePrepayInput) string {
	if strings.TrimSpace(input.RequestID) != "" {
		return strings.TrimSpace(input.RequestID)
	}
	return strings.TrimSpace(input.ClientRequestID)
}

func normalizePrepayInput(input CreateNativePrepayInput) CreateNativePrepayInput {
	input.UserID = strings.TrimSpace(input.UserID)
	input.PlanCode = strings.TrimSpace(input.PlanCode)
	input.BillingPeriod = strings.TrimSpace(input.BillingPeriod)
	input.ClientRequestID = strings.TrimSpace(input.ClientRequestID)
	input.RequestID = strings.TrimSpace(input.RequestID)
	input.PayerClientIP = strings.TrimSpace(input.PayerClientIP)
	return input
}

func nativePrepayResultFromOrder(order payment.Order) NativePrepayResult {
	return NativePrepayResult{
		OrderID: order.ID,
		OrderNo: order.OrderNo,
		Status:  order.Status,
		Amount: Amount{
			Currency: order.Currency,
			Total:    order.AmountCents,
		},
		Payment: paymentResultFromTransaction(order.ProviderTransaction),
	}
}

func orderResultFromOrder(order payment.Order) OrderResult {
	result := OrderResult{
		OrderID:       order.ID,
		OrderNo:       order.OrderNo,
		Status:        order.Status,
		PlanCode:      order.PlanCode,
		BillingPeriod: order.BillingPeriod,
		Amount:        Amount{Currency: order.Currency, Total: order.AmountCents},
		PaidAt:        order.PaidAt,
		ClosedAt:      order.ClosedAt,
		CreatedAt:     order.CreatedAt,
	}
	if order.ProviderTransaction != nil {
		paymentResult := paymentResultFromTransaction(order.ProviderTransaction)
		result.Payment = &paymentResult
	}
	return result
}

// paymentResultFromTransaction converts a provider transaction into an HTTP-facing payment object.
func paymentResultFromTransaction(transaction *payment.ProviderTransactionRecord) PaymentResult {
	if transaction == nil {
		return PaymentResult{Payload: map[string]any{}}
	}
	payload := transaction.PaymentPayload
	if payload == nil {
		payload = map[string]any{}
	}
	return PaymentResult{
		Provider:        transaction.Provider,
		Method:          transaction.PaymentMethod,
		MerchantOrderNo: transaction.MerchantOrderNo,
		Payload:         payload,
		ExpiresAt:       transaction.ExpiresAt,
	}
}

func existingPrepayExpired(order payment.Order, now time.Time) bool {
	if order.ProviderTransaction == nil || order.ProviderTransaction.ExpiresAt == nil {
		return false
	}
	return !order.ProviderTransaction.ExpiresAt.After(now)
}

// defaultOrderNo creates a compact UUIDv7 merchant order number for provider requests.
func defaultOrderNo(_ time.Time) (string, error) {
	value, err := uuid.NewV7()
	if err != nil {
		return "", fmt.Errorf("generate payment order number: %w", err)
	}
	return strings.ReplaceAll(value.String(), "-", ""), nil
}
