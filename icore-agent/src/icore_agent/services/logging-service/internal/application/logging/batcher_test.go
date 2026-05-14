package logging

import (
	"context"
	"sync"
	"testing"
	"time"

	domain "xiehe-logging-service/internal/domain/logging"
)

type recordingSink struct {
	mu      sync.Mutex
	batches [][]domain.LogEvent
}

func (sink *recordingSink) WriteBatch(_ context.Context, events []domain.LogEvent) error {
	sink.mu.Lock()
	defer sink.mu.Unlock()

	copied := append([]domain.LogEvent(nil), events...)
	sink.batches = append(sink.batches, copied)
	return nil
}

func (sink *recordingSink) count() int {
	sink.mu.Lock()
	defer sink.mu.Unlock()

	count := 0
	for _, batch := range sink.batches {
		count += len(batch)
	}
	return count
}

func TestServiceFlushesQueuedEventsOnInterval(t *testing.T) {
	sink := &recordingSink{}
	service := NewService(Config{
		FlushInterval: 25 * time.Millisecond,
		QueueSize:     10,
	}, []BatchSink{sink}, nil)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	service.Start(ctx)

	err := service.Ingest(ctx, []domain.LogEvent{
		{Timestamp: time.Now().UTC(), Level: domain.LogLevelInfo, Service: "backend", Message: "one", TraceID: "req-1", Metadata: map[string]any{}},
		{Timestamp: time.Now().UTC(), Level: domain.LogLevelError, Service: "backend", Message: "two", TraceID: "req-2", Metadata: map[string]any{}},
	})
	if err != nil {
		t.Fatalf("Ingest returned error: %v", err)
	}

	deadline := time.After(500 * time.Millisecond)
	for sink.count() < 2 {
		select {
		case <-deadline:
			t.Fatalf("expected 2 flushed events, got %d", sink.count())
		default:
			time.Sleep(10 * time.Millisecond)
		}
	}
}
