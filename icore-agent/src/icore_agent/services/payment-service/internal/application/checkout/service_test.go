package checkout

import (
	"context"
	"errors"
	"testing"
	"time"

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
	codeURL string
	calls   []ProviderPrepayRequest
}

func (provider *fakeProvider) PrepayNative(_ context.Context, request ProviderPrepayRequest) (ProviderPrepayResult, error) {
	provider.calls = append(provider.calls, request)
	return ProviderPrepayResult{CodeURL: provider.codeURL}, nil
}

func (provider *fakeProvider) CloseOrder(_ context.Context, _ string) error {
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
