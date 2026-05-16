package logging

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"
)

// Emitter sends one LogEvent to a logging sink.
type Emitter interface {
	Emit(context.Context, LogEvent) error
}

// LoggingServiceClientConfig configures the logging-service HTTP client.
type LoggingServiceClientConfig struct {
	BaseURL string
	Token   string
	Timeout time.Duration
	Client  *http.Client
}

// LoggingServiceClient delivers LogEvent objects to logging-service.
type LoggingServiceClient struct {
	baseURL string
	token   string
	client  *http.Client
}

// NewLoggingServiceClient creates a reusable HTTP client for logging-service.
func NewLoggingServiceClient(config LoggingServiceClientConfig) *LoggingServiceClient {
	timeout := config.Timeout
	if timeout <= 0 {
		timeout = 2 * time.Second
	}
	client := config.Client
	if client == nil {
		client = &http.Client{Timeout: timeout}
	}
	return &LoggingServiceClient{
		baseURL: strings.TrimRight(config.BaseURL, "/"),
		token:   config.Token,
		client:  client,
	}
}

// Emit posts one event using the logging-service v1 JSON contract.
func (client *LoggingServiceClient) Emit(ctx context.Context, event LogEvent) error {
	payload, err := json.Marshal(logEventIngestRequest{Event: event})
	if err != nil {
		return err
	}

	request, err := http.NewRequestWithContext(
		ctx,
		http.MethodPost,
		client.baseURL+"/v1/log-events",
		bytes.NewReader(payload),
	)
	if err != nil {
		return err
	}
	request.Header.Set("Content-Type", "application/json")
	if client.token != "" {
		request.Header.Set("X-Logging-Service-Token", client.token)
	}
	if event.TraceID != "" {
		request.Header.Set("X-Request-ID", event.TraceID)
	}

	response, err := client.client.Do(request)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.StatusCode >= http.StatusBadRequest {
		return fmt.Errorf("logging-service returned %d", response.StatusCode)
	}
	return nil
}
