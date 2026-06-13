package reconciliation

import (
	"context"
	"errors"
	"testing"
	"time"

	"icore-payment-service/internal/domain/payment"
)

type fakeRepository struct {
	orders       []payment.Order
	paid         []payment.ProviderNotification
	expired      []string
	closed       []string
	claimErr     error
	markPaidErr  error
	markCloseErr error
}

func (repo *fakeRepository) ClaimPendingReconciliationOrders(_ context.Context, limit int, now time.Time) ([]payment.Order, error) {
	if repo.claimErr != nil {
		return nil, repo.claimErr
	}
	if limit <= 0 || limit > len(repo.orders) {
		limit = len(repo.orders)
	}
	_ = now
	return append([]payment.Order(nil), repo.orders[:limit]...), nil
}

func (repo *fakeRepository) MarkPaidByProvider(_ context.Context, notification payment.ProviderNotification) (payment.Order, error) {
	repo.paid = append(repo.paid, notification)
	return payment.Order{OrderNo: notification.Transaction.MerchantOrderNo, Status: payment.StatusPaid}, repo.markPaidErr
}

func (repo *fakeRepository) MarkExpiredByProvider(_ context.Context, orderNo string, _ time.Time) (payment.Order, error) {
	repo.expired = append(repo.expired, orderNo)
	return payment.Order{OrderNo: orderNo, Status: payment.StatusExpired}, repo.markCloseErr
}

func (repo *fakeRepository) MarkClosedByProvider(_ context.Context, orderNo string, _ time.Time) (payment.Order, error) {
	repo.closed = append(repo.closed, orderNo)
	return payment.Order{OrderNo: orderNo, Status: payment.StatusClosed}, repo.markCloseErr
}

type fakeProvider struct {
	transactions map[string]payment.ProviderTransaction
	err          error
	queries      []string
	closed       []string
}

func (provider *fakeProvider) QueryOrderByOutTradeNo(_ context.Context, orderNo string) (payment.ProviderTransaction, error) {
	provider.queries = append(provider.queries, orderNo)
	if provider.err != nil {
		return payment.ProviderTransaction{}, provider.err
	}
	transaction, ok := provider.transactions[orderNo]
	if !ok {
		return payment.ProviderTransaction{MerchantOrderNo: orderNo, ProviderTradeState: "NOTPAY"}, nil
	}
	return transaction, nil
}

func (provider *fakeProvider) CloseOrder(_ context.Context, orderNo string) error {
	provider.closed = append(provider.closed, orderNo)
	return nil
}

func TestRunOnceMarksSuccessfulQueriedOrderPaid(t *testing.T) {
	now := time.Date(2026, 6, 13, 12, 0, 0, 0, time.UTC)
	repo := &fakeRepository{orders: []payment.Order{pendingOrder("wx202606130001", now.Add(10*time.Minute))}}
	provider := &fakeProvider{transactions: map[string]payment.ProviderTransaction{
		"wx202606130001": {
			AppID:                 "wx-app",
			MchID:                 "mch-1",
			Provider:              payment.ProviderWeChatPay,
			PaymentMethod:         payment.PaymentMethodNative,
			MerchantID:            "mch-1",
			MerchantOrderNo:       "wx202606130001",
			ProviderTransactionID: "4200000000202606130000000001",
			ProviderTradeState:    "SUCCESS",
			Currency:              "CNY",
			AmountCents:           19900,
			SuccessTime:           &now,
		},
	}}
	service := NewService(Config{
		Repository: repo,
		Provider:   provider,
		AppID:      "wx-app",
		MchID:      "mch-1",
		Now:        func() time.Time { return now },
		BatchSize:  10,
	})

	if err := service.RunOnce(context.Background()); err != nil {
		t.Fatalf("RunOnce returned error: %v", err)
	}

	if len(repo.paid) != 1 {
		t.Fatalf("paid notifications = %d, want 1", len(repo.paid))
	}
	notification := repo.paid[0]
	if notification.EventType != "payment.reconciliation.query" {
		t.Fatalf("event type = %q", notification.EventType)
	}
	if notification.Transaction.ProviderTransactionID != "4200000000202606130000000001" {
		t.Fatalf("transaction = %#v", notification.Transaction)
	}
}

func TestRunOnceClosesAndExpiresTimedOutNotPayOrder(t *testing.T) {
	now := time.Date(2026, 6, 13, 12, 0, 0, 0, time.UTC)
	repo := &fakeRepository{orders: []payment.Order{pendingOrder("wx202606130002", now.Add(-time.Minute))}}
	provider := &fakeProvider{transactions: map[string]payment.ProviderTransaction{
		"wx202606130002": {
			Provider:           payment.ProviderWeChatPay,
			PaymentMethod:      payment.PaymentMethodNative,
			MerchantID:         "mch-1",
			MerchantOrderNo:    "wx202606130002",
			ProviderTradeState: "NOTPAY",
			Currency:           "CNY",
			AmountCents:        19900,
		},
	}}
	service := NewService(Config{
		Repository: repo,
		Provider:   provider,
		AppID:      "wx-app",
		MchID:      "mch-1",
		Now:        func() time.Time { return now },
		BatchSize:  10,
	})

	if err := service.RunOnce(context.Background()); err != nil {
		t.Fatalf("RunOnce returned error: %v", err)
	}

	if len(provider.closed) != 1 || provider.closed[0] != "wx202606130002" {
		t.Fatalf("provider closed = %#v", provider.closed)
	}
	if len(repo.expired) != 1 || repo.expired[0] != "wx202606130002" {
		t.Fatalf("repo expired = %#v", repo.expired)
	}
}

func TestRunOnceMarksProviderClosedOrderClosed(t *testing.T) {
	now := time.Date(2026, 6, 13, 12, 0, 0, 0, time.UTC)
	repo := &fakeRepository{orders: []payment.Order{pendingOrder("wx202606130003", now.Add(10*time.Minute))}}
	provider := &fakeProvider{transactions: map[string]payment.ProviderTransaction{
		"wx202606130003": {
			Provider:           payment.ProviderWeChatPay,
			PaymentMethod:      payment.PaymentMethodNative,
			MerchantID:         "mch-1",
			MerchantOrderNo:    "wx202606130003",
			ProviderTradeState: "CLOSED",
			Currency:           "CNY",
			AmountCents:        19900,
		},
	}}
	service := NewService(Config{
		Repository: repo,
		Provider:   provider,
		AppID:      "wx-app",
		MchID:      "mch-1",
		Now:        func() time.Time { return now },
		BatchSize:  10,
	})

	if err := service.RunOnce(context.Background()); err != nil {
		t.Fatalf("RunOnce returned error: %v", err)
	}

	if len(repo.closed) != 1 || repo.closed[0] != "wx202606130003" {
		t.Fatalf("repo closed = %#v", repo.closed)
	}
}

func TestRunOnceKeepsPendingOrderAfterTransientQueryError(t *testing.T) {
	now := time.Date(2026, 6, 13, 12, 0, 0, 0, time.UTC)
	repo := &fakeRepository{orders: []payment.Order{pendingOrder("wx202606130004", now.Add(-time.Minute))}}
	provider := &fakeProvider{err: errors.New("wechat timeout")}
	service := NewService(Config{
		Repository: repo,
		Provider:   provider,
		AppID:      "wx-app",
		MchID:      "mch-1",
		Now:        func() time.Time { return now },
		BatchSize:  10,
	})

	if err := service.RunOnce(context.Background()); err != nil {
		t.Fatalf("RunOnce returned error: %v", err)
	}

	if len(repo.expired) != 0 || len(repo.closed) != 0 || len(repo.paid) != 0 {
		t.Fatalf("repo changed after transient error: %#v", repo)
	}
}

func pendingOrder(orderNo string, expiresAt time.Time) payment.Order {
	return payment.Order{
		ID:              "11111111-1111-1111-1111-111111111111",
		OrderNo:         orderNo,
		UserPublicID:    "user-1",
		PlanCode:        "pro",
		BillingPeriod:   "monthly",
		AmountCents:     19900,
		Currency:        "CNY",
		Status:          payment.StatusPending,
		ClientRequestID: "req-1",
		ProviderTransaction: &payment.ProviderTransactionRecord{
			ID:              "22222222-2222-2222-2222-222222222222",
			OrderID:         "11111111-1111-1111-1111-111111111111",
			Provider:        payment.ProviderWeChatPay,
			PaymentMethod:   payment.PaymentMethodNative,
			MerchantID:      "mch-1",
			MerchantOrderNo: orderNo,
			Status:          payment.StatusPending,
			PaymentPayload:  map[string]any{"code_url": "weixin://code"},
			ExpiresAt:       &expiresAt,
			CreatedAt:       expiresAt.Add(-30 * time.Minute),
			UpdatedAt:       expiresAt.Add(-30 * time.Minute),
		},
	}
}
