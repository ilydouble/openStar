package proxy

import (
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
	proxy.ServeHTTP(response, request)

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
