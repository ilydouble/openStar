package logging

import (
	"context"
	"errors"
	"log"
	"time"

	domain "xiehe-logging-service/internal/domain/logging"
)

// BatchSink writes a flushed batch to a local or external sink.
type BatchSink interface {
	WriteBatch(context.Context, []domain.LogEvent) error
}

// Publisher forwards accepted batches to Kafka or another event bus.
type Publisher interface {
	Publish(context.Context, []domain.LogEvent) error
}

// Config controls queue size and timed batch flushing behavior.
type Config struct {
	FlushInterval time.Duration
	QueueSize     int
	MaxBatchSize  int
}

// Service validates incoming events, batches them, and flushes them to sinks.
type Service struct {
	queue     chan []domain.LogEvent
	sinks     []BatchSink
	publisher Publisher
	config    Config
}

// NewService builds a logging service with conservative batching defaults.
func NewService(config Config, sinks []BatchSink, publisher Publisher) *Service {
	if config.FlushInterval <= 0 {
		config.FlushInterval = 500 * time.Millisecond
	}
	if config.QueueSize <= 0 {
		config.QueueSize = 1024
	}
	if config.MaxBatchSize <= 0 {
		config.MaxBatchSize = 256
	}

	return &Service{
		queue:     make(chan []domain.LogEvent, config.QueueSize),
		sinks:     sinks,
		publisher: publisher,
		config:    config,
	}
}

// Start launches the goroutine that drains queued events until the context stops.
func (service *Service) Start(ctx context.Context) {
	go service.run(ctx)
}

// Ingest validates events and enqueues them without performing disk or Kafka I/O inline.
func (service *Service) Ingest(ctx context.Context, events []domain.LogEvent) error {
	if len(events) == 0 {
		return errors.New("at least one event is required")
	}

	copied := make([]domain.LogEvent, 0, len(events))
	for _, event := range events {
		if event.Metadata == nil {
			event.Metadata = map[string]any{}
		}
		if err := domain.ValidateEvent(event); err != nil {
			return err
		}
		copied = append(copied, event)
	}

	select {
	case service.queue <- copied:
		return nil
	case <-ctx.Done():
		return ctx.Err()
	default:
		return errors.New("logging queue is full")
	}
}

// run accumulates events and flushes every configured interval or max batch size.
func (service *Service) run(ctx context.Context) {
	ticker := time.NewTicker(service.config.FlushInterval)
	defer ticker.Stop()

	pending := make([]domain.LogEvent, 0, service.config.MaxBatchSize)
	flush := func() {
		if len(pending) == 0 {
			return
		}
		batch := append([]domain.LogEvent(nil), pending...)
		pending = pending[:0]
		service.writeBatch(ctx, batch)
	}

	for {
		select {
		case events := <-service.queue:
			pending = append(pending, events...)
			if len(pending) >= service.config.MaxBatchSize {
				flush()
			}
		case <-ticker.C:
			flush()
		case <-ctx.Done():
			flush()
			return
		}
	}
}

// writeBatch fans a flushed batch out to configured sinks and publisher.
func (service *Service) writeBatch(ctx context.Context, events []domain.LogEvent) {
	for _, sink := range service.sinks {
		if err := sink.WriteBatch(ctx, events); err != nil {
			log.Printf("logging sink write failed: %v", err)
		}
	}
	if service.publisher != nil {
		if err := service.publisher.Publish(ctx, events); err != nil {
			log.Printf("kafka publish failed: %v", err)
		}
	}
}
