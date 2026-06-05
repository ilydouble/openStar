package checkout

import (
	"context"
	"errors"
	"testing"
	"time"

	"icore-payment-service/internal/application/paymentlog"
	"icore-payment-service/internal/domain/catalog"
	"icore-payment-service/internal/domain/payment"
)

type memoryOrderRepository struct {
	orders        map[string]payment.Order
	idempotencies map[string]string
}

func newMemoryOrderRepository() *memoryOrderRepository {
	return &memoryOrderRepository{
		orders:        map[string]payment.Order{},
		idempotencies: map[string]string{},
	}
}

func (repo *memoryOrderRepository) FindByIdempotencyKey(_ context.Context, key string) (payment.Order, error) {
	outTradeNo, ok := repo.idempotencies[key]
	if !ok {
		return payment.Order{}, payment.ErrOrderNotFound
	}
	return repo.orders[outTradeNo], nil
}

func (repo *memoryOrderRepository) FindByOutTradeNo(_ context.Context, outTradeNo string) (payment.Order, error) {
	order, ok := repo.orders[outTradeNo]
	if !ok {
		return payment.Order{}, payment.ErrOrderNotFound
	}
	return order, nil
}

func (repo *memoryOrderRepository) CreateOrder(_ context.Context, order payment.Order) error {
	if _, exists := repo.orders[order.OutTradeNo]; exists {
		return errors.New("duplicate out_trade_no")
	}
	repo.orders[order.OutTradeNo] = order
	repo.idempotencies[order.IdempotencyKey] = order.OutTradeNo
	return nil
}

func (repo *memoryOrderRepository) MarkPending(_ context.Context, outTradeNo string, codeURL string, expiresAt time.Time) (payment.Order, error) {
	order, ok := repo.orders[outTradeNo]
	if !ok {
		return payment.Order{}, payment.ErrOrderNotFound
	}
	order.Status = payment.StatusPending
	order.CodeURL = codeURL
	order.CodeURLExpiresAt = &expiresAt
	repo.orders[outTradeNo] = order
	return order, nil
}

func (repo *memoryOrderRepository) FindByOutTradeNoForUser(_ context.Context, outTradeNo string, userID string) (payment.Order, error) {
	order, ok := repo.orders[outTradeNo]
	if !ok || order.UserPublicID != userID {
		return payment.Order{}, payment.ErrOrderNotFound
	}
	return order, nil
}

func (repo *memoryOrderRepository) MarkClosed(_ context.Context, outTradeNo string, userID string, closedAt time.Time) (payment.Order, error) {
	order, ok := repo.orders[outTradeNo]
	if !ok || order.UserPublicID != userID {
		return payment.Order{}, payment.ErrOrderNotFound
	}
	order.Status = payment.StatusClosed
	order.ClosedAt = &closedAt
	repo.orders[outTradeNo] = order
	return order, nil
}

type fakeProvider struct {
	codeURL   string
	prepayErr error
	closeErr  error
	calls     []ProviderPrepayRequest
}

func (provider *fakeProvider) PrepayNative(_ context.Context, request ProviderPrepayRequest) (ProviderPrepayResult, error) {
	provider.calls = append(provider.calls, request)
	if provider.prepayErr != nil {
		return ProviderPrepayResult{}, provider.prepayErr
	}
	return ProviderPrepayResult{CodeURL: provider.codeURL}, nil
}

func (provider *fakeProvider) CloseOrder(_ context.Context, _ string) error {
	return provider.closeErr
}

type recordedLogEvent struct {
	level    string
	message  string
	traceID  string
	metadata map[string]any
}

type recordingLogger struct {
	events []recordedLogEvent
}

func (logger *recordingLogger) Info(_ context.Context, message string, traceID string, metadata map[string]any) error {
	logger.events = append(logger.events, recordedLogEvent{level: "info", message: message, traceID: traceID, metadata: metadata})
	return nil
}

func (logger *recordingLogger) Warning(_ context.Context, message string, traceID string, metadata map[string]any) error {
	logger.events = append(logger.events, recordedLogEvent{level: "warning", message: message, traceID: traceID, metadata: metadata})
	return nil
}

func (logger *recordingLogger) Error(_ context.Context, message string, traceID string, metadata map[string]any) error {
	logger.events = append(logger.events, recordedLogEvent{level: "error", message: message, traceID: traceID, metadata: metadata})
	return nil
}

func TestCreateNativePrepayCreatesPendingOrderFromCatalog(t *testing.T) {
	now := time.Date(2026, 6, 4, 12, 0, 0, 0, time.UTC)
	repo := newMemoryOrderRepository()
	provider := &fakeProvider{codeURL: "weixin://wxpay/bizpayurl?pr=test"}
	service := NewService(ServiceConfig{
		Catalog:    testCatalog(t),
		Repository: repo,
		Provider:   provider,
		AppID:      "wx-app",
		MchID:      "mch-1",
		NotifyURL:  "https://pay.example.com/webhooks/wechatpay/native",
		OrderTTL:   30 * time.Minute,
		Now:        func() time.Time { return now },
		NewOrderID: func() string { return "11111111-1111-1111-1111-111111111111" },
		NewOutTradeNo: func(time.Time) string {
			return "wx202606041200000000000001"
		},
	})

	result, err := service.CreateNativePrepay(context.Background(), CreateNativePrepayInput{
		UserID:          "user-1",
		PlanCode:        "pro",
		BillingPeriod:   "monthly",
		ClientRequestID: "req-1",
		PayerClientIP:   "203.0.113.10",
	})
	if err != nil {
		t.Fatalf("CreateNativePrepay returned error: %v", err)
	}

	if result.OutTradeNo != "wx202606041200000000000001" || result.CodeURL != provider.codeURL || result.Status != payment.StatusPending {
		t.Fatalf("result = %#v", result)
	}
	if result.Amount.Total != 19900 || result.Amount.Currency != "CNY" {
		t.Fatalf("amount = %#v", result.Amount)
	}
	if len(provider.calls) != 1 {
		t.Fatalf("provider calls = %d, want 1", len(provider.calls))
	}
	call := provider.calls[0]
	if call.AmountCents != 19900 || call.Currency != "CNY" || call.Description != "Pro monthly" {
		t.Fatalf("provider request = %#v", call)
	}
	if call.OutTradeNo != result.OutTradeNo || call.PayerClientIP != "203.0.113.10" {
		t.Fatalf("provider request identity = %#v", call)
	}
}

func TestCreateNativePrepayReturnsExistingPendingOrderForSameIdempotencyKey(t *testing.T) {
	now := time.Date(2026, 6, 4, 12, 0, 0, 0, time.UTC)
	repo := newMemoryOrderRepository()
	provider := &fakeProvider{codeURL: "weixin://wxpay/bizpayurl?pr=test"}
	service := NewService(ServiceConfig{
		Catalog:    testCatalog(t),
		Repository: repo,
		Provider:   provider,
		AppID:      "wx-app",
		MchID:      "mch-1",
		NotifyURL:  "https://pay.example.com/webhooks/wechatpay/native",
		OrderTTL:   30 * time.Minute,
		Now:        func() time.Time { return now },
		NewOrderID: func() string { return "11111111-1111-1111-1111-111111111111" },
		NewOutTradeNo: func(time.Time) string {
			return "wx202606041200000000000001"
		},
	})

	first, err := service.CreateNativePrepay(context.Background(), CreateNativePrepayInput{
		UserID:          "user-1",
		PlanCode:        "pro",
		BillingPeriod:   "monthly",
		ClientRequestID: "req-1",
	})
	if err != nil {
		t.Fatalf("first prepay returned error: %v", err)
	}
	second, err := service.CreateNativePrepay(context.Background(), CreateNativePrepayInput{
		UserID:          "user-1",
		PlanCode:        "pro",
		BillingPeriod:   "monthly",
		ClientRequestID: "req-1",
	})
	if err != nil {
		t.Fatalf("second prepay returned error: %v", err)
	}

	if second.OutTradeNo != first.OutTradeNo || second.CodeURL != first.CodeURL {
		t.Fatalf("second = %#v, first = %#v", second, first)
	}
	if len(provider.calls) != 1 {
		t.Fatalf("provider calls = %d, want 1", len(provider.calls))
	}
}

func TestCreateNativePrepayRetriesProviderForExistingCreatedOrder(t *testing.T) {
	now := time.Date(2026, 6, 4, 12, 0, 0, 0, time.UTC)
	repo := newMemoryOrderRepository()
	key := payment.IdempotencyKey("user-1", "pro", "monthly", "req-1")
	repo.orders["wx202606041200000000000001"] = payment.Order{
		ID:              "11111111-1111-1111-1111-111111111111",
		OutTradeNo:      "wx202606041200000000000001",
		UserPublicID:    "user-1",
		PlanCode:        "pro",
		BillingPeriod:   "monthly",
		AmountCents:     19900,
		Currency:        "CNY",
		Status:          payment.StatusCreated,
		ClientRequestID: "req-1",
		IdempotencyKey:  key,
		CreatedAt:       now,
		UpdatedAt:       now,
	}
	repo.idempotencies[key] = "wx202606041200000000000001"
	provider := &fakeProvider{codeURL: "weixin://wxpay/bizpayurl?pr=retry"}
	service := NewService(ServiceConfig{
		Catalog:    testCatalog(t),
		Repository: repo,
		Provider:   provider,
		AppID:      "wx-app",
		MchID:      "mch-1",
		NotifyURL:  "https://pay.example.com/webhooks/wechatpay/native",
		OrderTTL:   30 * time.Minute,
		Now:        func() time.Time { return now },
	})

	result, err := service.CreateNativePrepay(context.Background(), CreateNativePrepayInput{
		UserID:          "user-1",
		PlanCode:        "pro",
		BillingPeriod:   "monthly",
		ClientRequestID: "req-1",
	})
	if err != nil {
		t.Fatalf("CreateNativePrepay returned error: %v", err)
	}

	if result.Status != payment.StatusPending || result.CodeURL != provider.codeURL {
		t.Fatalf("result = %#v", result)
	}
	if len(provider.calls) != 1 {
		t.Fatalf("provider calls = %d, want 1", len(provider.calls))
	}
	if provider.calls[0].OutTradeNo != "wx202606041200000000000001" {
		t.Fatalf("provider out_trade_no = %q", provider.calls[0].OutTradeNo)
	}
}

func TestCreateNativePrepayLogsProviderErrorWithWrappedMetadata(t *testing.T) {
	now := time.Date(2026, 6, 4, 12, 0, 0, 0, time.UTC)
	repo := newMemoryOrderRepository()
	provider := &fakeProvider{prepayErr: &payment.ProviderError{
		Provider:       payment.ProviderWeChatPay,
		API:            "native.prepay",
		HTTPStatus:     403,
		Code:           "NO_AUTH",
		Message:        "merchant payment function is limited",
		RequestID:      "wechat-request-id",
		ResponseSerial: "wechatpay-public-key-serial",
	}}
	logger := &recordingLogger{}
	service := NewService(ServiceConfig{
		Catalog:    testCatalog(t),
		Repository: repo,
		Provider:   provider,
		Logger:     logger,
		AppID:      "wx-app",
		MchID:      "mch-1",
		NotifyURL:  "https://pay.example.com/webhooks/wechatpay/native",
		OrderTTL:   30 * time.Minute,
		Now:        func() time.Time { return now },
		NewOrderID: func() string { return "11111111-1111-1111-1111-111111111111" },
		NewOutTradeNo: func(time.Time) string {
			return "wx202606041200000000000001"
		},
	})

	_, err := service.CreateNativePrepay(context.Background(), CreateNativePrepayInput{
		UserID:          "user-1",
		PlanCode:        "pro",
		BillingPeriod:   "monthly",
		ClientRequestID: "client-request-id",
		RequestID:       "gateway-request-id",
		PayerClientIP:   "203.0.113.10",
	})
	if err == nil {
		t.Fatal("CreateNativePrepay returned nil error, want provider error")
	}

	if len(logger.events) != 1 {
		t.Fatalf("log events = %d, want 1", len(logger.events))
	}
	event := logger.events[0]
	if event.level != "error" || event.message != "payment provider prepay failed" || event.traceID != "gateway-request-id" {
		t.Fatalf("event identity = %#v", event)
	}
	providerMetadata, ok := event.metadata["provider"].(paymentlog.ProviderMetadata)
	if !ok {
		t.Fatalf("provider metadata = %#v, want paymentlog.ProviderMetadata", event.metadata["provider"])
	}
	if providerMetadata.Name != payment.ProviderWeChatPay || providerMetadata.API != "native.prepay" {
		t.Fatalf("provider metadata identity = %#v", providerMetadata)
	}
	if providerMetadata.Error == nil || providerMetadata.Error.Code != "NO_AUTH" || providerMetadata.Error.HTTPStatus != 403 {
		t.Fatalf("provider error metadata = %#v", providerMetadata.Error)
	}
	if providerMetadata.RequestID != "wechat-request-id" || providerMetadata.ResponseSerial != "wechatpay-public-key-serial" {
		t.Fatalf("provider correlation metadata = %#v", providerMetadata)
	}
	orderMetadata, ok := event.metadata["order"].(paymentlog.OrderMetadata)
	if !ok {
		t.Fatalf("order metadata = %#v, want paymentlog.OrderMetadata", event.metadata["order"])
	}
	if orderMetadata.OutTradeNo != "wx202606041200000000000001" || orderMetadata.AmountCents != 19900 {
		t.Fatalf("order metadata = %#v", orderMetadata)
	}
	requestMetadata, ok := event.metadata["request"].(paymentlog.RequestMetadata)
	if !ok {
		t.Fatalf("request metadata = %#v, want paymentlog.RequestMetadata", event.metadata["request"])
	}
	if requestMetadata.ClientRequestID != "client-request-id" || requestMetadata.PayerClientIP != "203.0.113.10" {
		t.Fatalf("request metadata = %#v", requestMetadata)
	}
}

func testCatalog(t *testing.T) catalog.Catalog {
	t.Helper()
	cat, err := catalog.NewCatalog([]catalog.Item{
		{
			PlanCode:            "pro",
			BillingPeriod:       "monthly",
			Currency:            "CNY",
			AmountCents:         19900,
			Description:         "Pro monthly",
			EntitlementsVersion: "account-plans-v2",
			Enabled:             true,
		},
	})
	if err != nil {
		t.Fatalf("NewCatalog returned error: %v", err)
	}
	return cat
}
