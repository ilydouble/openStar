package wechatpay

import (
	"encoding/json"
	"errors"
	"net/http"
	"net/url"
	"strings"
	"testing"
	"time"

	"icore-payment-service/internal/application/paymentlog"
	"icore-payment-service/internal/domain/payment"

	"github.com/wechatpay-apiv3/wechatpay-go/core"
	"github.com/wechatpay-apiv3/wechatpay-go/services/payments"
)

type roundTripFunc func(*http.Request) (*http.Response, error)

func (fn roundTripFunc) RoundTrip(request *http.Request) (*http.Response, error) {
	return fn(request)
}

func TestAPIHostRewriteTransportTargetsConfiguredSandboxHost(t *testing.T) {
	sandboxURL, err := url.Parse("https://wechatpay-sandbox.example.test")
	if err != nil {
		t.Fatalf("parse sandbox URL: %v", err)
	}
	var seenURL string
	transport := newAPIHostRewriteTransport(roundTripFunc(func(request *http.Request) (*http.Response, error) {
		seenURL = request.URL.String()
		return &http.Response{StatusCode: http.StatusOK, Header: http.Header{}, Body: http.NoBody}, nil
	}), sandboxURL)

	request, err := http.NewRequest(http.MethodPost, "https://api.mch.weixin.qq.com/v3/pay/transactions/native", nil)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	_, err = transport.RoundTrip(request)
	if err != nil {
		t.Fatalf("round trip: %v", err)
	}

	want := "https://wechatpay-sandbox.example.test/v3/pay/transactions/native"
	if seenURL != want {
		t.Fatalf("rewritten URL = %q, want %q", seenURL, want)
	}
}

func TestProviderErrorFromAPIErrorKeepsSafeWechatPayFields(t *testing.T) {
	apiErr := &core.APIError{
		StatusCode: http.StatusForbidden,
		Header: http.Header{
			"Request-Id":          []string{"wechat-request-id"},
			"Wechatpay-Serial":    []string{"wechatpay-public-key-serial"},
			"Wechatpay-Signature": []string{"must-not-be-copied"},
		},
		Code:    "NO_AUTH",
		Message: "merchant payment function is limited",
	}

	err := newProviderError("native.prepay", apiErr)

	var providerErr *payment.ProviderError
	if !errors.As(err, &providerErr) {
		t.Fatalf("error = %T, want payment.ProviderError", err)
	}
	if providerErr.Provider != payment.ProviderWeChatPay || providerErr.API != "native.prepay" {
		t.Fatalf("provider error identity = %#v", providerErr)
	}
	if providerErr.HTTPStatus != http.StatusForbidden || providerErr.Code != "NO_AUTH" || providerErr.Message != "merchant payment function is limited" {
		t.Fatalf("provider error details = %#v", providerErr)
	}
	if providerErr.RequestID != "wechat-request-id" || providerErr.ResponseSerial != "wechatpay-public-key-serial" {
		t.Fatalf("provider error correlation = %#v", providerErr)
	}
	metadata := paymentlog.ProviderMetadataFromError(payment.ProviderWeChatPay, "merchant-1", "native.prepay", err)
	payload, marshalErr := json.Marshal(metadata)
	if marshalErr != nil {
		t.Fatalf("marshal metadata: %v", marshalErr)
	}
	if strings.Contains(string(payload), "must-not-be-copied") || strings.Contains(string(payload), "Wechatpay-Signature") {
		t.Fatalf("metadata payload copied signature: %s", string(payload))
	}
}

func TestProviderTransactionFromWechatPayTransactionMapsQueryResult(t *testing.T) {
	successTime := "2026-06-13T12:00:00+08:00"
	transaction := &payments.Transaction{
		Appid:         core.String("wx-app"),
		Mchid:         core.String("mch-1"),
		OutTradeNo:    core.String("wx202606130001"),
		TransactionId: core.String("4200000000202606130000000001"),
		TradeState:    core.String("SUCCESS"),
		SuccessTime:   core.String(successTime),
		Amount: &payments.TransactionAmount{
			Total:    core.Int64(19900),
			Currency: core.String("CNY"),
		},
	}

	result := providerTransactionFromWechatPayTransaction("mch-1", transaction)

	if result.AppID != "wx-app" || result.MchID != "mch-1" {
		t.Fatalf("app/merchant = %#v", result)
	}
	if result.Provider != payment.ProviderWeChatPay || result.PaymentMethod != payment.PaymentMethodNative {
		t.Fatalf("provider identity = %#v", result)
	}
	if result.MerchantOrderNo != "wx202606130001" || result.ProviderTransactionID != "4200000000202606130000000001" {
		t.Fatalf("order identity = %#v", result)
	}
	if result.ProviderTradeState != "SUCCESS" || result.AmountCents != 19900 || result.Currency != "CNY" {
		t.Fatalf("transaction fields = %#v", result)
	}
	wantSuccessTime := time.Date(2026, 6, 13, 4, 0, 0, 0, time.UTC)
	if result.SuccessTime == nil || !result.SuccessTime.Equal(wantSuccessTime) {
		t.Fatalf("success time = %v, want %v", result.SuccessTime, wantSuccessTime)
	}
}
