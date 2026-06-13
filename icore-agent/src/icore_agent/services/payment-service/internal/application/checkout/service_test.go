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
	orders               map[string]payment.Order
	providerTransactions map[string]payment.ProviderTransactionRecord
	idempotencies        map[string]string
}

func newMemoryOrderRepository() *memoryOrderRepository {
	return &memoryOrderRepository{
		orders:               map[string]payment.Order{},
		providerTransactions: map[string]payment.ProviderTransactionRecord{},
		idempotencies:        map[string]string{},
	}
}

func (repo *memoryOrderRepository) FindByIdempotencyKey(_ context.Context, key string) (payment.Order, error) {
	orderNo, ok := repo.idempotencies[key]
	if !ok {
		return payment.Order{}, payment.ErrOrderNotFound
	}
	return repo.orderWithPayment(orderNo), nil
}

func (repo *memoryOrderRepository) FindByOrderNo(_ context.Context, orderNo string) (payment.Order, error) {
	order, ok := repo.orders[orderNo]
	if !ok {
		return payment.Order{}, payment.ErrOrderNotFound
	}
	order.ProviderTransaction = repo.providerTransactionForOrder(order.ID)
	return order, nil
}

func (repo *memoryOrderRepository) CreateOrder(_ context.Context, order payment.Order) error {
	if _, exists := repo.orders[order.OrderNo]; exists {
		return errors.New("duplicate order_no")
	}
	repo.orders[order.OrderNo] = order
	repo.idempotencies[order.IdempotencyKey] = order.OrderNo
	return nil
}

func (repo *memoryOrderRepository) MarkProviderPending(_ context.Context, orderNo string, transaction payment.ProviderTransactionRecord) (payment.Order, error) {
	order, ok := repo.orders[orderNo]
	if !ok {
		return payment.Order{}, payment.ErrOrderNotFound
	}
	order.Status = payment.StatusPending
	repo.orders[orderNo] = order
	transaction.OrderID = order.ID
	repo.providerTransactions[order.ID] = transaction
	return repo.orderWithPayment(orderNo), nil
}

func (repo *memoryOrderRepository) FindByOrderNoForUser(_ context.Context, orderNo string, userID string) (payment.Order, error) {
	order, ok := repo.orders[orderNo]
	if !ok || order.UserPublicID != userID {
		return payment.Order{}, payment.ErrOrderNotFound
	}
	order.ProviderTransaction = repo.providerTransactionForOrder(order.ID)
	return order, nil
}

func (repo *memoryOrderRepository) MarkClosed(_ context.Context, orderNo string, userID string, closedAt time.Time) (payment.Order, error) {
	order, ok := repo.orders[orderNo]
	if !ok || order.UserPublicID != userID {
		return payment.Order{}, payment.ErrOrderNotFound
	}
	order.Status = payment.StatusClosed
	order.ClosedAt = &closedAt
	repo.orders[orderNo] = order
	return repo.orderWithPayment(orderNo), nil
}

func (repo *memoryOrderRepository) MarkExpiredByProvider(_ context.Context, orderNo string, expiredAt time.Time) (payment.Order, error) {
	order, ok := repo.orders[orderNo]
	if !ok {
		return payment.Order{}, payment.ErrOrderNotFound
	}
	order.Status = payment.StatusExpired
	order.ClosedAt = &expiredAt
	repo.orders[orderNo] = order
	if transaction := repo.providerTransactionForOrder(order.ID); transaction != nil {
		transaction.Status = payment.StatusExpired
		transaction.ClosedAt = &expiredAt
		repo.providerTransactions[order.ID] = *transaction
	}
	return repo.orderWithPayment(orderNo), nil
}

func (repo *memoryOrderRepository) orderWithPayment(orderNo string) payment.Order {
	order := repo.orders[orderNo]
	order.ProviderTransaction = repo.providerTransactionForOrder(order.ID)
	return order
}

func (repo *memoryOrderRepository) providerTransactionForOrder(orderID string) *payment.ProviderTransactionRecord {
	transaction, ok := repo.providerTransactions[orderID]
	if !ok {
		return nil
	}
	return &transaction
}

type fakeProvider struct {
	codeURL   string
	prepayErr error
	closeErr  error
	closed    []string
	calls     []ProviderPrepayRequest
}

func (provider *fakeProvider) PrepayNative(_ context.Context, request ProviderPrepayRequest) (ProviderPrepayResult, error) {
	provider.calls = append(provider.calls, request)
	if provider.prepayErr != nil {
		return ProviderPrepayResult{}, provider.prepayErr
	}
	return ProviderPrepayResult{CodeURL: provider.codeURL}, nil
}

func (provider *fakeProvider) CloseOrder(_ context.Context, orderNo string) error {
	provider.closed = append(provider.closed, orderNo)
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
		NewOrderNo: func(time.Time) (string, error) {
			return "wx202606041200000000000001", nil
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

	if result.OrderNo != "wx202606041200000000000001" || result.Status != payment.StatusPending {
		t.Fatalf("result = %#v", result)
	}
	if result.Payment.Provider != payment.ProviderWeChatPay || result.Payment.Payload["code_url"] != provider.codeURL {
		t.Fatalf("payment = %#v", result.Payment)
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
	if call.MerchantOrderNo != result.OrderNo || call.PayerClientIP != "203.0.113.10" {
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
		NewOrderNo: func(time.Time) (string, error) {
			return "wx202606041200000000000001", nil
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

	if second.OrderNo != first.OrderNo || second.Payment.Payload["code_url"] != first.Payment.Payload["code_url"] {
		t.Fatalf("second = %#v, first = %#v", second, first)
	}
	if len(provider.calls) != 1 {
		t.Fatalf("provider calls = %d, want 1", len(provider.calls))
	}
}

func TestCreateNativePrepayRejectsExpiredPendingOrderForSameIdempotencyKey(t *testing.T) {
	now := time.Date(2026, 6, 4, 12, 30, 0, 0, time.UTC)
	expiredAt := now.Add(-time.Minute)
	repo := newMemoryOrderRepository()
	key := payment.IdempotencyKey("user-1", "pro", "monthly", "req-1")
	repo.orders["wx202606041200000000000001"] = payment.Order{
		ID:              "11111111-1111-1111-1111-111111111111",
		OrderNo:         "wx202606041200000000000001",
		UserPublicID:    "user-1",
		PlanCode:        "pro",
		BillingPeriod:   "monthly",
		AmountCents:     19900,
		Currency:        "CNY",
		Status:          payment.StatusPending,
		ClientRequestID: "req-1",
		IdempotencyKey:  key,
		CreatedAt:       now.Add(-time.Hour),
		UpdatedAt:       now.Add(-time.Hour),
	}
	repo.idempotencies[key] = "wx202606041200000000000001"
	repo.providerTransactions["11111111-1111-1111-1111-111111111111"] = payment.ProviderTransactionRecord{
		ID:              "22222222-2222-2222-2222-222222222222",
		OrderID:         "11111111-1111-1111-1111-111111111111",
		Provider:        payment.ProviderWeChatPay,
		PaymentMethod:   payment.PaymentMethodNative,
		MerchantID:      "mch-1",
		MerchantOrderNo: "wx202606041200000000000001",
		Status:          payment.StatusPending,
		PaymentPayload:  map[string]any{"code_url": "weixin://expired"},
		ExpiresAt:       &expiredAt,
		CreatedAt:       now.Add(-time.Hour),
		UpdatedAt:       now.Add(-time.Hour),
	}
	provider := &fakeProvider{codeURL: "weixin://new-code-url"}
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

	_, err := service.CreateNativePrepay(context.Background(), CreateNativePrepayInput{
		UserID:          "user-1",
		PlanCode:        "pro",
		BillingPeriod:   "monthly",
		ClientRequestID: "req-1",
	})

	if !errors.Is(err, payment.ErrPaymentOrderExpired) {
		t.Fatalf("CreateNativePrepay error = %v, want ErrPaymentOrderExpired", err)
	}
	if len(provider.calls) != 0 {
		t.Fatalf("provider prepay calls = %d, want 0", len(provider.calls))
	}
	if len(provider.closed) != 1 || provider.closed[0] != "wx202606041200000000000001" {
		t.Fatalf("provider closed = %#v", provider.closed)
	}
	if got := repo.orders["wx202606041200000000000001"].Status; got != payment.StatusExpired {
		t.Fatalf("order status = %s, want expired", got)
	}
}

func TestCreateNativePrepayRetriesProviderForExistingCreatedOrder(t *testing.T) {
	now := time.Date(2026, 6, 4, 12, 0, 0, 0, time.UTC)
	repo := newMemoryOrderRepository()
	key := payment.IdempotencyKey("user-1", "pro", "monthly", "req-1")
	repo.orders["wx202606041200000000000001"] = payment.Order{
		ID:              "11111111-1111-1111-1111-111111111111",
		OrderNo:         "wx202606041200000000000001",
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

	if result.Status != payment.StatusPending || result.Payment.Payload["code_url"] != provider.codeURL {
		t.Fatalf("result = %#v", result)
	}
	if len(provider.calls) != 1 {
		t.Fatalf("provider calls = %d, want 1", len(provider.calls))
	}
	if provider.calls[0].MerchantOrderNo != "wx202606041200000000000001" {
		t.Fatalf("provider merchant_order_no = %q", provider.calls[0].MerchantOrderNo)
	}
}

func TestDefaultOrderNoUsesCollisionResistantUUID7Value(t *testing.T) {
	now := time.Date(2026, 6, 4, 12, 0, 0, 0, time.UTC)

	first, err := defaultOrderNo(now)
	if err != nil {
		t.Fatalf("defaultOrderNo first returned error: %v", err)
	}
	second, err := defaultOrderNo(now)
	if err != nil {
		t.Fatalf("defaultOrderNo second returned error: %v", err)
	}

	if first == second {
		t.Fatalf("defaultOrderNo generated duplicate values for same timestamp: %q", first)
	}
	if len(first) != 32 || len(second) != 32 {
		t.Fatalf("order numbers = %q/%q, want 32 characters", first, second)
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
		NewOrderNo: func(time.Time) (string, error) {
			return "wx202606041200000000000001", nil
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
	if orderMetadata.OrderNo != "wx202606041200000000000001" || orderMetadata.AmountCents != 19900 {
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
