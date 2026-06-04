package notification

import (
	"context"
	"net/http"
	"testing"

	"icore-payment-service/internal/domain/payment"
)

type fakeNotificationProvider struct {
	notification payment.ProviderNotification
}

func (provider fakeNotificationProvider) ParseNotification(_ context.Context, _ *http.Request) (payment.ProviderNotification, error) {
	return provider.notification, nil
}

type recordingNotificationRepository struct {
	calls []payment.ProviderNotification
}

func (repo *recordingNotificationRepository) MarkPaidByProvider(_ context.Context, notification payment.ProviderNotification) (payment.Order, error) {
	repo.calls = append(repo.calls, notification)
	return payment.Order{OutTradeNo: notification.Transaction.OutTradeNo, Status: payment.StatusPaid}, nil
}

func TestHandleWechatPayNativePersistsVerifiedSuccessNotification(t *testing.T) {
	repo := &recordingNotificationRepository{}
	service := NewService(ServiceConfig{
		AppID:      "wx-app",
		MchID:      "mch-1",
		Provider:   fakeNotificationProvider{notification: successNotification()},
		Repository: repo,
	})

	if err := service.HandleWechatPayNative(context.Background(), &http.Request{}); err != nil {
		t.Fatalf("HandleWechatPayNative returned error: %v", err)
	}

	if len(repo.calls) != 1 {
		t.Fatalf("repo calls = %d, want 1", len(repo.calls))
	}
	if repo.calls[0].EventID != "evt-1" || repo.calls[0].Transaction.TransactionID != "4200001" {
		t.Fatalf("notification = %#v", repo.calls[0])
	}
}

func TestHandleWechatPayNativeRejectsMerchantMismatch(t *testing.T) {
	repo := &recordingNotificationRepository{}
	notification := successNotification()
	notification.Transaction.MchID = "other-mch"
	service := NewService(ServiceConfig{
		AppID:      "wx-app",
		MchID:      "mch-1",
		Provider:   fakeNotificationProvider{notification: notification},
		Repository: repo,
	})

	err := service.HandleWechatPayNative(context.Background(), &http.Request{})
	if err == nil {
		t.Fatal("HandleWechatPayNative returned nil error, want mismatch")
	}
	if len(repo.calls) != 0 {
		t.Fatalf("repo calls = %d, want 0", len(repo.calls))
	}
}

func successNotification() payment.ProviderNotification {
	return payment.ProviderNotification{
		EventID:   "evt-1",
		EventType: "TRANSACTION.SUCCESS",
		Transaction: payment.ProviderTransaction{
			AppID:         "wx-app",
			MchID:         "mch-1",
			OutTradeNo:    "wx202606041200000000000001",
			TransactionID: "4200001",
			TradeState:    "SUCCESS",
			Currency:      "CNY",
			AmountCents:   19900,
		},
		RawPayload: []byte(`{"out_trade_no":"wx202606041200000000000001"}`),
	}
}
