package logging

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"strings"
	"testing"
	"time"
)

func TestLoggingServiceClientEmitsEventToLoggingService(t *testing.T) {
	t.Helper()

	var capturedPath string
	var capturedToken string
	var capturedRequestID string
	var capturedPayload logEventIngestRequest

	transport := roundTripFunc(func(r *http.Request) (*http.Response, error) {
		capturedPath = r.URL.Path
		capturedToken = r.Header.Get("X-Logging-Service-Token")
		capturedRequestID = r.Header.Get("X-Request-ID")
		if err := json.NewDecoder(r.Body).Decode(&capturedPayload); err != nil {
			t.Fatalf("decode payload: %v", err)
		}
		return &http.Response{
			StatusCode: http.StatusOK,
			Header:     make(http.Header),
			Body:       io.NopCloser(strings.NewReader(`{"accepted":1}`)),
		}, nil
	})

	client := NewLoggingServiceClient(LoggingServiceClientConfig{
		BaseURL: "http://logging-service:8091",
		Token:   "service-token",
		Client:  &http.Client{Transport: transport},
	})
	event := LogEvent{
		Timestamp: time.Date(2026, 5, 16, 15, 22, 0, 0, time.FixedZone("CST", 8*3600)),
		Level:     LogLevelInfo,
		Service:   "icore-gateway",
		Message:   "gateway request",
		TraceID:   "req-1",
		Metadata: struct {
			RequestID string `json:"request_id"`
		}{RequestID: "req-1"},
	}

	if err := client.Emit(context.Background(), event); err != nil {
		t.Fatalf("emit event: %v", err)
	}

	if capturedPath != "/v1/log-events" {
		t.Fatalf("path = %q, want /v1/log-events", capturedPath)
	}
	if capturedToken != "service-token" {
		t.Fatalf("token header = %q, want service-token", capturedToken)
	}
	if capturedRequestID != "req-1" {
		t.Fatalf("request id header = %q, want req-1", capturedRequestID)
	}
	if capturedPayload.Event.Service != "icore-gateway" {
		t.Fatalf("service = %q, want icore-gateway", capturedPayload.Event.Service)
	}
	if capturedPayload.Event.TraceID != "req-1" {
		t.Fatalf("trace id = %q, want req-1", capturedPayload.Event.TraceID)
	}
}

type roundTripFunc func(*http.Request) (*http.Response, error)

func (fn roundTripFunc) RoundTrip(request *http.Request) (*http.Response, error) {
	return fn(request)
}
