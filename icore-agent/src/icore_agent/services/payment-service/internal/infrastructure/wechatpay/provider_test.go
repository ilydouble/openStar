package wechatpay

import (
	"net/http"
	"net/url"
	"testing"
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
