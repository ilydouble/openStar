package httpapi

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

const testAllowedOrigin = "https://app.example.com"

// TestCORSMiddlewareHandlesAllowedPreflight verifies preflight stops before downstream work.
func TestCORSMiddlewareHandlesAllowedPreflight(t *testing.T) {
	downstreamHit := false
	handler := CORSMiddleware(CORSConfig{AllowedOrigins: []string{testAllowedOrigin}})(
		http.HandlerFunc(func(http.ResponseWriter, *http.Request) {
			downstreamHit = true
		}),
	)
	request := httptest.NewRequest(http.MethodOptions, "/api/v1/account/me", nil)
	request.Header.Set("Origin", testAllowedOrigin)
	request.Header.Set("Access-Control-Request-Method", http.MethodGet)
	request.Header.Set("Access-Control-Request-Headers", "authorization,x-request-id")
	response := httptest.NewRecorder()

	handler.ServeHTTP(response, request)

	if response.Code != http.StatusNoContent {
		t.Fatalf("status = %d, want 204", response.Code)
	}
	if downstreamHit {
		t.Fatal("preflight should not reach downstream handler")
	}
	if got := response.Header().Get("Access-Control-Allow-Origin"); got != testAllowedOrigin {
		t.Fatalf("allow origin = %q", got)
	}
	if got := response.Header().Get("Access-Control-Allow-Headers"); got != "authorization,x-request-id" {
		t.Fatalf("allow headers = %q", got)
	}
	if got := response.Header().Get("Access-Control-Allow-Credentials"); got != "true" {
		t.Fatalf("allow credentials = %q", got)
	}
	if got := response.Header().Get("Access-Control-Max-Age"); got != "600" {
		t.Fatalf("max age = %q", got)
	}
}

// TestCORSMiddlewareRejectsDisallowedPreflight verifies untrusted origins never reach upstream.
func TestCORSMiddlewareRejectsDisallowedPreflight(t *testing.T) {
	downstreamHit := false
	handler := CORSMiddleware(CORSConfig{AllowedOrigins: []string{testAllowedOrigin}})(
		http.HandlerFunc(func(http.ResponseWriter, *http.Request) {
			downstreamHit = true
		}),
	)
	request := httptest.NewRequest(http.MethodOptions, "/api/v1/account/me", nil)
	request.Header.Set("Origin", "https://attacker.example.com")
	request.Header.Set("Access-Control-Request-Method", http.MethodGet)
	response := httptest.NewRecorder()

	handler.ServeHTTP(response, request)

	if response.Code != http.StatusForbidden {
		t.Fatalf("status = %d, want 403", response.Code)
	}
	if downstreamHit {
		t.Fatal("disallowed preflight should not reach downstream handler")
	}
	if got := response.Header().Get("Access-Control-Allow-Origin"); got != "" {
		t.Fatalf("allow origin = %q, want empty", got)
	}
	if got := response.Header().Values("Vary"); len(got) != 3 {
		t.Fatalf("vary = %#v, want origin and preflight dimensions", got)
	}
}

// TestCORSMiddlewarePassesNonCORSOptions verifies service OPTIONS traffic is unchanged.
func TestCORSMiddlewarePassesNonCORSOptions(t *testing.T) {
	downstreamHit := false
	handler := CORSMiddleware(CORSConfig{AllowedOrigins: []string{testAllowedOrigin}})(
		http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
			downstreamHit = true
			w.WriteHeader(http.StatusAccepted)
		}),
	)
	request := httptest.NewRequest(http.MethodOptions, "/api/v1/account/me", nil)
	response := httptest.NewRecorder()

	handler.ServeHTTP(response, request)

	if response.Code != http.StatusAccepted || !downstreamHit {
		t.Fatalf("status = %d, downstream = %t", response.Code, downstreamHit)
	}
}

// TestCORSMiddlewareDecoratesActualErrors verifies browsers can read gateway failures.
func TestCORSMiddlewareDecoratesActualErrors(t *testing.T) {
	handler := CORSMiddleware(CORSConfig{AllowedOrigins: []string{testAllowedOrigin}})(
		http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
			w.WriteHeader(http.StatusUnauthorized)
		}),
	)
	request := httptest.NewRequest(http.MethodGet, "/api/v1/account/me", nil)
	request.Header.Set("Origin", testAllowedOrigin)
	response := httptest.NewRecorder()

	handler.ServeHTTP(response, request)

	if response.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401", response.Code)
	}
	if got := response.Header().Get("Access-Control-Allow-Origin"); got != testAllowedOrigin {
		t.Fatalf("allow origin = %q", got)
	}
	if got := response.Header().Get("Access-Control-Expose-Headers"); got != "X-Request-ID" {
		t.Fatalf("expose headers = %q", got)
	}
}
