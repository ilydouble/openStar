package proxy

import (
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

type roundTripFunc func(*http.Request) (*http.Response, error)

func (fn roundTripFunc) RoundTrip(request *http.Request) (*http.Response, error) {
	return fn(request)
}

func TestReverseProxyForwardsToConfiguredBackend(t *testing.T) {
	var upstreamHost string
	var upstreamPath string
	proxy := NewReverseProxy("http://backend.local", roundTripFunc(func(request *http.Request) (*http.Response, error) {
		upstreamHost = request.Host
		upstreamPath = request.URL.Path
		return &http.Response{
			StatusCode: http.StatusAccepted,
			Header:     make(http.Header),
			Body:       io.NopCloser(strings.NewReader(`{"ok":true}`)),
		}, nil
	}))

	response := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodPost, "/api/v1/account/login", nil)
	proxy.ServeHTTP(response, request, "http://backend.local")

	if response.Code != http.StatusAccepted {
		t.Fatalf("status = %d, want 202", response.Code)
	}
	if upstreamHost != "backend.local" {
		t.Fatalf("host = %q, want backend.local", upstreamHost)
	}
	if upstreamPath != "/api/v1/account/login" {
		t.Fatalf("path = %q, want login path", upstreamPath)
	}
}

func TestReverseProxyForwardsToSelectedPaymentUpstream(t *testing.T) {
	var upstreamHost string
	proxy := NewReverseProxy("http://backend.local", roundTripFunc(func(request *http.Request) (*http.Response, error) {
		upstreamHost = request.Host
		return &http.Response{
			StatusCode: http.StatusOK,
			Header:     make(http.Header),
			Body:       io.NopCloser(strings.NewReader(`{"ok":true}`)),
		}, nil
	}))

	response := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodPost, "/api/v1/payment/native/prepay", nil)
	proxy.ServeHTTP(response, request, "http://payment.local")

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", response.Code)
	}
	if upstreamHost != "payment.local" {
		t.Fatalf("host = %q, want payment.local", upstreamHost)
	}
}

// TestReverseProxyErrorUsesApiEnvelope verifies gateway proxy failures.
func TestReverseProxyErrorUsesApiEnvelope(t *testing.T) {
	proxy := NewReverseProxy("http://backend.local", roundTripFunc(func(request *http.Request) (*http.Response, error) {
		return nil, errors.New("dial failed")
	}))

	response := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodPost, "/api/v1/account/login", nil)
	proxy.ServeHTTP(response, request, "http://backend.local")

	if response.Code != http.StatusBadGateway {
		t.Fatalf("status = %d, want 502", response.Code)
	}
	var payload map[string]any
	if err := json.Unmarshal(response.Body.Bytes(), &payload); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if payload["code"] != float64(http.StatusBadGateway) {
		t.Fatalf("code = %#v, want 502", payload["code"])
	}
	if payload["message"] != "upstream unavailable" {
		t.Fatalf("message = %#v", payload["message"])
	}
	if payload["data"] != nil {
		t.Fatalf("data = %#v, want nil", payload["data"])
	}
	if payload["error_code"] != http.StatusText(http.StatusBadGateway) {
		t.Fatalf("error_code = %#v", payload["error_code"])
	}
}
