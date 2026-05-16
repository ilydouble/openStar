package logging

import (
	"context"
	"errors"
	"log"
	"sync"
	"time"

	domain "icore-gateway/internal/domain/gateway"
	sharedlogging "icore-services-lib-go/logging"
)

// Config controls asynchronous gateway access log delivery.
type Config struct {
	Emitter   sharedlogging.Emitter
	Timeout   time.Duration
	QueueSize int
}

// AsyncAccessLogger buffers access log events and delivers them from a worker.
type AsyncAccessLogger struct {
	emitter sharedlogging.Emitter
	timeout time.Duration
	queue   chan domain.AccessLogEvent
	done    chan struct{}

	mu        sync.RWMutex
	closed    bool
	closeOnce sync.Once
}

// NewAsyncAccessLogger creates and starts an asynchronous access log sink.
func NewAsyncAccessLogger(config Config) *AsyncAccessLogger {
	timeout := config.Timeout
	if timeout <= 0 {
		timeout = 2 * time.Second
	}
	queueSize := config.QueueSize
	if queueSize <= 0 {
		queueSize = 4096
	}
	logger := &AsyncAccessLogger{
		emitter: config.Emitter,
		timeout: timeout,
		queue:   make(chan domain.AccessLogEvent, queueSize),
		done:    make(chan struct{}),
	}
	go logger.run()
	return logger
}

// Emit enqueues one access log event without blocking the request path.
func (logger *AsyncAccessLogger) Emit(event domain.AccessLogEvent) {
	logger.mu.RLock()
	defer logger.mu.RUnlock()
	if logger.closed {
		log.Printf("gateway access log sink is closed; dropping request_id=%s", event.TraceID)
		return
	}
	select {
	case logger.queue <- event:
	default:
		log.Printf("gateway access log queue is full; dropping request_id=%s", event.TraceID)
	}
}

// Close stops accepting events and waits for the worker to drain queued events.
func (logger *AsyncAccessLogger) Close(ctx context.Context) error {
	logger.closeOnce.Do(func() {
		logger.mu.Lock()
		logger.closed = true
		close(logger.queue)
		logger.mu.Unlock()
	})

	select {
	case <-logger.done:
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}

func (logger *AsyncAccessLogger) run() {
	defer close(logger.done)
	for event := range logger.queue {
		if logger.emitter == nil {
			continue
		}
		ctx, cancel := context.WithTimeout(context.Background(), logger.timeout)
		err := logger.emitter.Emit(ctx, event.ToLogEvent())
		cancel()
		if err != nil && !errors.Is(err, context.Canceled) {
			log.Printf("gateway access log emit failed: %v", err)
		}
	}
}
