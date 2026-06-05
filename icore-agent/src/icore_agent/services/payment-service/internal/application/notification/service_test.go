package notification

import (
	"context"
	"errors"
	"net/http"
	"testing"

	"icore-payment-service/internal/application/paymentlog"
	"icore-payment-service/internal/domain/payment"
)

type fakeNotificationProvider struct {
	notification payment.ProviderNotification
	err          error
}

func (provider fakeNotificationProvider) ParseNotification(_ context.Context, _ *http.Request) (payment.ProviderNotification, error) {
	if provider.err != nil {
		return payment.ProviderNotification{}, provider.err
	}
	return provider.notification, nil
}

type recordingNotificationRepository struct {
	calls []payment.ProviderNotification
}

func (repo *recordingNotificationRepository) MarkPaidByProvider(_ context.Context, notification payment.ProviderNotification) (payment.Order, error) {
	repo.calls = append(repo.calls, notification)
	return payment.Order{OrderNo: notification.Transaction.MerchantOrderNo, Status: payment.StatusPaid}, nil
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
	if repo.calls[0].EventID != "evt-1" || repo.calls[0].Transaction.ProviderTransactionID != "4200001" {
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

func TestHandleWechatPayNativeLogsProviderParseErrorWithWrappedMetadata(t *testing.T) {
	logger := &recordingLogger{}
	service := NewService(ServiceConfig{
		AppID:      "wx-app",
		MchID:      "mch-1",
		Provider:   fakeNotificationProvider{err: errors.New("signature validation failed")},
		Repository: &recordingNotificationRepository{},
		Logger:     logger,
	})
	request, err := http.NewRequest(http.MethodPost, "/webhooks/wechatpay/native", nil)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	request.Header.Set("X-Request-ID", "gateway-request-id")

	err = service.HandleWechatPayNative(context.Background(), request)
	if err == nil {
		t.Fatal("HandleWechatPayNative returned nil error, want parse error")
	}

	if len(logger.events) != 1 {
		t.Fatalf("log events = %d, want 1", len(logger.events))
	}
	event := logger.events[0]
	if event.level != "warning" || event.message != "payment provider notification parse failed" || event.traceID != "gateway-request-id" {
		t.Fatalf("event identity = %#v", event)
	}
	providerMetadata, ok := event.metadata["provider"].(paymentlog.ProviderMetadata)
	if !ok {
		t.Fatalf("provider metadata = %#v, want paymentlog.ProviderMetadata", event.metadata["provider"])
	}
	if providerMetadata.Name != payment.ProviderWeChatPay || providerMetadata.API != "native.notification" {
		t.Fatalf("provider metadata identity = %#v", providerMetadata)
	}
	if providerMetadata.Error == nil || providerMetadata.Error.Message != "signature validation failed" {
		t.Fatalf("provider error metadata = %#v", providerMetadata.Error)
	}
}

func successNotification() payment.ProviderNotification {
	return payment.ProviderNotification{
		EventID:   "evt-1",
		EventType: "TRANSACTION.SUCCESS",
		Transaction: payment.ProviderTransaction{
			AppID:                 "wx-app",
			MchID:                 "mch-1",
			Provider:              payment.ProviderWeChatPay,
			PaymentMethod:         payment.PaymentMethodNative,
			MerchantID:            "mch-1",
			MerchantOrderNo:       "wx202606041200000000000001",
			ProviderTransactionID: "4200001",
			ProviderTradeState:    "SUCCESS",
			Currency:              "CNY",
			AmountCents:           19900,
		},
		RawPayload: []byte(`{"merchant_order_no":"wx202606041200000000000001"}`),
	}
}
