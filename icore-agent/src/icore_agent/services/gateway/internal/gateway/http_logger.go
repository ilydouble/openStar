package gateway

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"
)

type logEventIngestRequest struct {
	Event LogEvent `json:"event"`
}

// HTTPLogger sends gateway log events to logging-service using the v1 JSON contract.
type HTTPLogger struct {
	baseURL string
	token   string
	client  *http.Client
}

// NewHTTPLogger creates a logging-service client for gateway access logs.
func NewHTTPLogger(baseURL string, token string, timeout time.Duration) *HTTPLogger {
	if timeout <= 0 {
		timeout = 2 * time.Second
	}
	return &HTTPLogger{
		baseURL: strings.TrimRight(baseURL, "/"),
		token:   token,
		client:  &http.Client{Timeout: timeout},
	}
}

// Emit posts one log event to logging-service.
func (logger *HTTPLogger) Emit(ctx context.Context, event LogEvent) error {
	payload, err := json.Marshal(logEventIngestRequest{Event: event})
	if err != nil {
		return err
	}

	request, err := http.NewRequestWithContext(
		ctx,
		http.MethodPost,
		logger.baseURL+"/v1/log-events",
		bytes.NewReader(payload),
	)
	if err != nil {
		return err
	}
	request.Header.Set("Content-Type", "application/json")
	if logger.token != "" {
		request.Header.Set("X-Logging-Service-Token", logger.token)
	}
	if event.TraceID != "" {
		request.Header.Set("X-Request-ID", event.TraceID)
	}

	response, err := logger.client.Do(request)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.StatusCode >= http.StatusBadRequest {
		return fmt.Errorf("logging-service returned %d", response.StatusCode)
	}
	return nil
}
