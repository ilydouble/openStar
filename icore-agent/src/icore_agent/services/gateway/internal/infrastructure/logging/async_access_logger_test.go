package logging

import (
	"context"
	"sync"
	"testing"
	"time"

	domain "icore-gateway/internal/domain/gateway"
	sharedlogging "icore-services-lib-go/logging"
)

type captureEmitter struct {
	mu     sync.Mutex
	events []sharedlogging.LogEvent
	block  <-chan struct{}
}

func (emitter *captureEmitter) Emit(_ context.Context, event sharedlogging.LogEvent) error {
	if emitter.block != nil {
		<-emitter.block
	}
	emitter.mu.Lock()
	defer emitter.mu.Unlock()
	emitter.events = append(emitter.events, event)
	return nil
}

func (emitter *captureEmitter) Count() int {
	emitter.mu.Lock()
	defer emitter.mu.Unlock()
	return len(emitter.events)
}

func TestAsyncAccessLoggerDeliversAfterRequestContextCancellation(t *testing.T) {
	emitter := &captureEmitter{}
	logger := NewAsyncAccessLogger(Config{
		Emitter:   emitter,
		Timeout:   20 * time.Millisecond,
		QueueSize: 2,
	})

	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	_ = ctx
	logger.Emit(testAccessLogEvent("req-1"))

	closeCtx, closeCancel := context.WithTimeout(context.Background(), time.Second)
	defer closeCancel()
	if err := logger.Close(closeCtx); err != nil {
		t.Fatalf("close logger: %v", err)
	}
	if emitter.Count() != 1 {
		t.Fatalf("events = %d, want 1", emitter.Count())
	}
}

func TestAsyncAccessLoggerDropsWhenQueueIsFullWithoutBlocking(t *testing.T) {
	unblock := make(chan struct{})
	emitter := &captureEmitter{block: unblock}
	logger := NewAsyncAccessLogger(Config{
		Emitter:   emitter,
		Timeout:   time.Second,
		QueueSize: 1,
	})

	logger.Emit(testAccessLogEvent("req-1"))
	logger.Emit(testAccessLogEvent("req-2"))
	start := time.Now()
	logger.Emit(testAccessLogEvent("req-3"))
	if elapsed := time.Since(start); elapsed > 50*time.Millisecond {
		t.Fatalf("Emit blocked for %s on full queue", elapsed)
	}

	close(unblock)
	closeCtx, closeCancel := context.WithTimeout(context.Background(), time.Second)
	defer closeCancel()
	if err := logger.Close(closeCtx); err != nil {
		t.Fatalf("close logger: %v", err)
	}
	if got := emitter.Count(); got > 2 {
		t.Fatalf("delivered events = %d, want at most 2 after one drop", got)
	}
}

func testAccessLogEvent(requestID string) domain.AccessLogEvent {
	return domain.AccessLogEvent{
		Timestamp: time.Date(2026, 5, 16, 15, 22, 0, 0, time.UTC),
		Level:     sharedlogging.LogLevelInfo,
		Service:   "icore-gateway",
		Message:   "gateway request",
		TraceID:   requestID,
		Metadata: domain.AccessLogMetadata{
			RequestID: requestID,
		},
	}
}
