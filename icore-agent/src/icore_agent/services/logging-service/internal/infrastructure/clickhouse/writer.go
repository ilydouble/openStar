package clickhouse

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"

	domain "icore-logging-service/internal/domain/logging"
)

// HTTPWriter inserts log batches into ClickHouse over the HTTP JSONEachRow API.
type HTTPWriter struct {
	baseURL  string
	database string
	table    string
	username string
	password string
	client   *http.Client
	now      func() time.Time
}

// HTTPWriterConfig configures the ClickHouse HTTP insert path.
type HTTPWriterConfig struct {
	BaseURL  string
	Database string
	Table    string
	Username string
	Password string
	Timeout  time.Duration
	Client   *http.Client
	Now      func() time.Time
}

// NewHTTPWriter creates a ClickHouse JSONEachRow batch writer.
func NewHTTPWriter(config HTTPWriterConfig) *HTTPWriter {
	timeout := config.Timeout
	if timeout <= 0 {
		timeout = 5 * time.Second
	}
	client := config.Client
	if client == nil {
		client = &http.Client{Timeout: timeout}
	}
	now := config.Now
	if now == nil {
		now = func() time.Time { return time.Now().UTC() }
	}
	return &HTTPWriter{
		baseURL:  strings.TrimRight(config.BaseURL, "/"),
		database: config.Database,
		table:    config.Table,
		username: config.Username,
		password: config.Password,
		client:   client,
		now:      now,
	}
}

// InsertEvents writes a decoded event batch and returns only after ClickHouse accepts it.
func (writer *HTTPWriter) InsertEvents(ctx context.Context, events []domain.LogEvent) error {
	if len(events) == 0 {
		return nil
	}

	var body bytes.Buffer
	buffered := bufio.NewWriter(&body)
	encoder := json.NewEncoder(buffered)
	for _, event := range events {
		metadata, err := json.Marshal(event.Metadata)
		if err != nil {
			return err
		}
		if err := encoder.Encode(clickHouseLogRow{
			EventID:      event.EventID,
			Timestamp:    formatClickHouseTime(event.Timestamp),
			Level:        string(event.Level),
			Service:      event.Service,
			Message:      event.Message,
			TraceID:      event.TraceID,
			MetadataJSON: string(metadata),
			IngestedAt:   formatClickHouseTime(writer.now()),
		}); err != nil {
			return err
		}
	}
	if err := buffered.Flush(); err != nil {
		return err
	}

	requestURL, err := writer.insertURL()
	if err != nil {
		return err
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodPost, requestURL, &body)
	if err != nil {
		return err
	}
	request.Header.Set("Content-Type", "application/json")
	if writer.username != "" {
		request.SetBasicAuth(writer.username, writer.password)
	}

	response, err := writer.client.Do(request)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.StatusCode >= http.StatusBadRequest {
		return fmt.Errorf("clickhouse insert returned %d", response.StatusCode)
	}
	return nil
}

func (writer *HTTPWriter) insertURL() (string, error) {
	parsed, err := url.Parse(writer.baseURL)
	if err != nil {
		return "", err
	}
	query := parsed.Query()
	if writer.database != "" {
		query.Set("database", writer.database)
	}
	query.Set("query", fmt.Sprintf("INSERT INTO %s FORMAT JSONEachRow", writer.table))
	parsed.RawQuery = query.Encode()
	return parsed.String(), nil
}

func formatClickHouseTime(value time.Time) string {
	return value.UTC().Format("2006-01-02 15:04:05.000")
}

type clickHouseLogRow struct {
	EventID      string `json:"event_id"`
	Timestamp    string `json:"timestamp"`
	Level        string `json:"level"`
	Service      string `json:"service"`
	Message      string `json:"message"`
	TraceID      string `json:"trace_id"`
	MetadataJSON string `json:"metadata_json"`
	IngestedAt   string `json:"ingested_at"`
}
