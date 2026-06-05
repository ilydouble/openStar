package checkout

import (
	"context"
	"errors"
	"fmt"
	"math/rand"
	"strconv"
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
	FindByOutTradeNo(context.Context, string) (payment.Order, error)
	CreateOrder(context.Context, payment.Order) error
	MarkPending(context.Context, string, string, time.Time) (payment.Order, error)
	FindByOutTradeNoForUser(context.Context, string, string) (payment.Order, error)
	MarkClosed(context.Context, string, string, time.Time) (payment.Order, error)
}

// Provider creates and closes provider-side payment orders.
type Provider interface {
	PrepayNative(context.Context, ProviderPrepayRequest) (ProviderPrepayResult, error)
	CloseOrder(context.Context, string) error
}

// ServiceConfig wires checkout service dependencies and defaults.
type ServiceConfig struct {
	Catalog       catalog.Catalog
	Repository    Repository
	Provider      Provider
	Logger        paymentlog.Logger
	AppID         string
	MchID         string
	NotifyURL     string
	OrderTTL      time.Duration
	Now           func() time.Time
	NewOrderID    func() string
	NewOutTradeNo func(time.Time) string
}

// Service owns payment checkout use cases.
type Service struct {
	catalog       catalog.Catalog
	repository    Repository
	provider      Provider
	logger        paymentlog.Logger
	appID         string
	mchID         string
	notifyURL     string
	orderTTL      time.Duration
	now           func() time.Time
	newOrderID    func() string
	newOutTradeNo func(time.Time) string
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
	UserID     string
	OutTradeNo string
}

// CloseOrderInput identifies a user-scoped order close request.
type CloseOrderInput struct {
	UserID     string
	OutTradeNo string
	RequestID  string
}

// ProviderPrepayRequest is the provider-neutral WeChat Native prepay request.
type ProviderPrepayRequest struct {
	AppID         string
	MchID         string
	Description   string
	OutTradeNo    string
	TimeExpire    time.Time
	NotifyURL     string
	AmountCents   int64
	Currency      string
	Attach        string
	PayerClientIP string
}

// ProviderPrepayResult is the provider-neutral WeChat Native prepay response.
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
	OrderID    string         `json:"order_id"`
	OutTradeNo string         `json:"out_trade_no"`
	CodeURL    string         `json:"code_url"`
	Status     payment.Status `json:"status"`
	Amount     Amount         `json:"amount"`
	ExpiresAt  *time.Time     `json:"expires_at"`
}

// OrderResult is the user-facing representation of one payment order.
type OrderResult struct {
	OrderID             string         `json:"order_id"`
	OutTradeNo          string         `json:"out_trade_no"`
	Status              payment.Status `json:"status"`
	PlanCode            string         `json:"plan_code"`
	BillingPeriod       string         `json:"billing_period"`
	Amount              Amount         `json:"amount"`
	CodeURL             string         `json:"code_url,omitempty"`
	CodeURLExpiresAt    *time.Time     `json:"code_url_expires_at,omitempty"`
	WechatTransactionID string         `json:"wechat_transaction_id,omitempty"`
	WechatTradeState    string         `json:"wechat_trade_state,omitempty"`
	PaidAt              *time.Time     `json:"paid_at,omitempty"`
	ClosedAt            *time.Time     `json:"closed_at,omitempty"`
	CreatedAt           time.Time      `json:"created_at"`
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
	newOutTradeNo := config.NewOutTradeNo
	if newOutTradeNo == nil {
		newOutTradeNo = defaultOutTradeNo
	}
	return &Service{
		catalog:       config.Catalog,
		repository:    config.Repository,
		provider:      config.Provider,
		logger:        config.Logger,
		appID:         strings.TrimSpace(config.AppID),
		mchID:         strings.TrimSpace(config.MchID),
		notifyURL:     strings.TrimSpace(config.NotifyURL),
		orderTTL:      orderTTL,
		now:           now,
		newOrderID:    newOrderID,
		newOutTradeNo: newOutTradeNo,
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
		if existing.ReusableForPrepay() {
			return nativePrepayResultFromOrder(existing), nil
		}
		return NativePrepayResult{}, payment.ErrInvalidOrderState
	}
	if !errors.Is(err, payment.ErrOrderNotFound) {
		return NativePrepayResult{}, err
	}

	now := service.now().UTC()
	order := payment.Order{
		ID:              service.newOrderID(),
		OutTradeNo:      service.newOutTradeNo(now),
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

func (service *Service) createProviderPrepay(ctx context.Context, order payment.Order, item catalog.Item, input CreateNativePrepayInput) (NativePrepayResult, error) {
	expiresAt := service.now().UTC().Add(service.orderTTL)
	providerResult, err := service.provider.PrepayNative(ctx, ProviderPrepayRequest{
		AppID:         service.appID,
		MchID:         service.mchID,
		Description:   item.Description,
		OutTradeNo:    order.OutTradeNo,
		TimeExpire:    expiresAt,
		NotifyURL:     service.notifyURL,
		AmountCents:   item.AmountCents,
		Currency:      item.Currency,
		Attach:        item.EntitlementsVersion,
		PayerClientIP: input.PayerClientIP,
	})
	if err != nil {
		service.logProviderError(ctx, "payment provider prepay failed", traceIDForPrepay(input), paymentlog.OperationNativePrepay, order, input, err)
		return NativePrepayResult{}, fmt.Errorf("wechat native prepay: %w", err)
	}
	pendingOrder, err := service.repository.MarkPending(ctx, order.OutTradeNo, providerResult.CodeURL, expiresAt)
	if err != nil {
		return NativePrepayResult{}, err
	}
	return nativePrepayResultFromOrder(pendingOrder), nil
}

// GetOrder returns one user-scoped payment order.
func (service *Service) GetOrder(ctx context.Context, input GetOrderInput) (OrderResult, error) {
	userID := strings.TrimSpace(input.UserID)
	outTradeNo := strings.TrimSpace(input.OutTradeNo)
	if userID == "" || outTradeNo == "" {
		return OrderResult{}, ErrInvalidRequest
	}
	order, err := service.repository.FindByOutTradeNoForUser(ctx, outTradeNo, userID)
	if err != nil {
		return OrderResult{}, err
	}
	return orderResultFromOrder(order), nil
}

// CloseOrder closes one user-scoped unpaid payment order.
func (service *Service) CloseOrder(ctx context.Context, input CloseOrderInput) (OrderResult, error) {
	userID := strings.TrimSpace(input.UserID)
	outTradeNo := strings.TrimSpace(input.OutTradeNo)
	if userID == "" || outTradeNo == "" {
		return OrderResult{}, ErrInvalidRequest
	}
	order, err := service.repository.FindByOutTradeNoForUser(ctx, outTradeNo, userID)
	if err != nil {
		return OrderResult{}, err
	}
	if order.Status == payment.StatusPaid {
		return OrderResult{}, payment.ErrInvalidOrderState
	}
	if order.Status != payment.StatusClosed && service.provider != nil {
		if err := service.provider.CloseOrder(ctx, outTradeNo); err != nil {
			service.logProviderError(ctx, "payment provider close order failed", strings.TrimSpace(input.RequestID), paymentlog.OperationCloseOrder, order, CreateNativePrepayInput{
				UserID:          userID,
				PlanCode:        order.PlanCode,
				BillingPeriod:   order.BillingPeriod,
				ClientRequestID: order.ClientRequestID,
			}, err)
			return OrderResult{}, fmt.Errorf("wechat close order: %w", err)
		}
	}
	closed, err := service.repository.MarkClosed(ctx, outTradeNo, userID, service.now().UTC())
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
		OrderID:    order.ID,
		OutTradeNo: order.OutTradeNo,
		CodeURL:    order.CodeURL,
		Status:     order.Status,
		Amount: Amount{
			Currency: order.Currency,
			Total:    order.AmountCents,
		},
		ExpiresAt: order.CodeURLExpiresAt,
	}
}

func orderResultFromOrder(order payment.Order) OrderResult {
	return OrderResult{
		OrderID:             order.ID,
		OutTradeNo:          order.OutTradeNo,
		Status:              order.Status,
		PlanCode:            order.PlanCode,
		BillingPeriod:       order.BillingPeriod,
		Amount:              Amount{Currency: order.Currency, Total: order.AmountCents},
		CodeURL:             order.CodeURL,
		CodeURLExpiresAt:    order.CodeURLExpiresAt,
		WechatTransactionID: order.WechatTransactionID,
		WechatTradeState:    order.WechatTradeState,
		PaidAt:              order.PaidAt,
		ClosedAt:            order.ClosedAt,
		CreatedAt:           order.CreatedAt,
	}
}

func defaultOutTradeNo(now time.Time) string {
	random := rand.New(rand.NewSource(now.UnixNano()))
	suffix := strconv.FormatInt(random.Int63(), 36)
	value := "wx" + now.UTC().Format("20060102150405") + suffix
	if len(value) > 32 {
		return value[:32]
	}
	return value
}
