package httpv1

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"icore-payment-service/internal/application/checkout"
	"icore-payment-service/internal/domain/payment"
)

type fakeCheckoutService struct {
	received checkout.CreateNativePrepayInput
}

func (service *fakeCheckoutService) CreateNativePrepay(_ context.Context, input checkout.CreateNativePrepayInput) (checkout.NativePrepayResult, error) {
	service.received = input
	expiresAt := time.Date(2026, 6, 4, 12, 30, 0, 0, time.UTC)
	return checkout.NativePrepayResult{
		OrderID:    "11111111-1111-1111-1111-111111111111",
		OutTradeNo: "wx202606041200000000000001",
		CodeURL:    "weixin://wxpay/bizpayurl?pr=test",
		Status:     payment.StatusPending,
		Amount: checkout.Amount{
			Currency: "CNY",
			Total:    19900,
		},
		ExpiresAt: &expiresAt,
	}, nil
}

func (service *fakeCheckoutService) GetOrder(_ context.Context, _ checkout.GetOrderInput) (checkout.OrderResult, error) {
	return checkout.OrderResult{}, payment.ErrOrderNotFound
}

func (service *fakeCheckoutService) CloseOrder(_ context.Context, _ checkout.CloseOrderInput) (checkout.OrderResult, error) {
	return checkout.OrderResult{}, payment.ErrOrderNotFound
}

func TestPrepayRequiresTrustedGatewayUserID(t *testing.T) {
	router := NewRouter(HandlerConfig{Checkout: &fakeCheckoutService{}})

	request := httptest.NewRequest(http.MethodPost, "/api/v1/payment/native/prepay", bytes.NewBufferString(`{"plan_code":"pro","billing_period":"monthly","client_request_id":"req-1"}`))
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)

	if response.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401", response.Code)
	}
	var body envelope
	if err := json.Unmarshal(response.Body.Bytes(), &body); err != nil {
		t.Fatalf("response body is not JSON: %v", err)
	}
	if body.ErrorCode == nil || *body.ErrorCode != "missing_user_id" {
		t.Fatalf("error_code = %#v", body.ErrorCode)
	}
}

func TestPrepayUsesTrustedGatewayUserIDAndReturnsEnvelope(t *testing.T) {
	service := &fakeCheckoutService{}
	router := NewRouter(HandlerConfig{Checkout: service})

	request := httptest.NewRequest(http.MethodPost, "/api/v1/payment/native/prepay", bytes.NewBufferString(`{
		"plan_code": "pro",
		"billing_period": "monthly",
		"client_request_id": "req-1",
		"user_id": "spoofed-client-user"
	}`))
	request.Header.Set("X-User-ID", "gateway-user-1")
	request.Header.Set("X-Forwarded-For", "198.51.100.7, 10.0.0.10")
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)

	if response.Code != http.StatusCreated {
		t.Fatalf("status = %d, want 201 body=%s", response.Code, response.Body.String())
	}
	if service.received.UserID != "gateway-user-1" {
		t.Fatalf("service user id = %q", service.received.UserID)
	}
	if service.received.PayerClientIP != "198.51.100.7" {
		t.Fatalf("payer client ip = %q", service.received.PayerClientIP)
	}

	var body envelope
	if err := json.Unmarshal(response.Body.Bytes(), &body); err != nil {
		t.Fatalf("response body is not JSON: %v", err)
	}
	data, ok := body.Data.(map[string]any)
	if !ok {
		t.Fatalf("data = %#v", body.Data)
	}
	if data["out_trade_no"] != "wx202606041200000000000001" || data["code_url"] == "" {
		t.Fatalf("data = %#v", data)
	}
}
