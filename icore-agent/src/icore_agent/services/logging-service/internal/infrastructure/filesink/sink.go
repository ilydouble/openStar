package filesink

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"sync"

	domain "xiehe-logging-service/internal/domain/logging"
)

// Filter decides whether a sink should persist a specific event.
type Filter func(domain.LogEvent) bool

// Sink appends filtered log events to a JSONL file.
type Sink struct {
	path   string
	filter Filter
	mu     sync.Mutex
}

// New creates a file sink for the target path and optional filter.
func New(path string, filter Filter) *Sink {
	return &Sink{path: path, filter: filter}
}

// ErrorAndAuditOnly keeps ERROR and AUDIT events for durable local archive.
func ErrorAndAuditOnly(event domain.LogEvent) bool {
	return event.Level == domain.LogLevelError || event.Level == domain.LogLevelAudit
}

// AllEvents keeps every event, which is useful for the local spool file.
func AllEvents(domain.LogEvent) bool {
	return true
}

// WriteBatch filters a batch and appends the selected events as JSON lines.
func (sink *Sink) WriteBatch(_ context.Context, events []domain.LogEvent) error {
	filtered := make([]domain.LogEvent, 0, len(events))
	for _, event := range events {
		if sink.filter == nil || sink.filter(event) {
			filtered = append(filtered, event)
		}
	}
	if len(filtered) == 0 {
		return nil
	}

	sink.mu.Lock()
	defer sink.mu.Unlock()

	if err := os.MkdirAll(filepath.Dir(sink.path), 0o755); err != nil {
		return err
	}
	file, err := os.OpenFile(sink.path, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if err != nil {
		return err
	}
	defer file.Close()

	encoder := json.NewEncoder(file)
	for _, event := range filtered {
		if err := encoder.Encode(event); err != nil {
			return err
		}
	}
	return nil
}
