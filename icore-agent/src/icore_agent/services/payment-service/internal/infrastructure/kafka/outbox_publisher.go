package kafka

import (
	"context"
	"log"
	"time"

	postgresrepo "icore-payment-service/internal/infrastructure/persistence/postgres"
	sharedkafka "icore-services-lib-go/mq/kafka"
)

// OutboxStore exposes the repository methods needed by the publisher loop.
type OutboxStore interface {
	ClaimPendingOutbox(context.Context, int) ([]postgresrepo.OutboxMessage, error)
	MarkOutboxPublished(context.Context, string) error
	MarkOutboxFailed(context.Context, string, error) error
}

// Producer publishes serialized outbox messages to the event bus.
type Producer interface {
	Publish(context.Context, []sharedkafka.Message) error
}

// Logger records outbox publisher operational failures.
type Logger interface {
	Printf(string, ...any)
}

// PublisherConfig configures outbox batch publishing.
type PublisherConfig struct {
	BatchSize      int
	PublishTimeout time.Duration
	Logger         Logger
}

// Publisher sends transactional outbox messages to Kafka.
type Publisher struct {
	store          OutboxStore
	producer       Producer
	batchSize      int
	publishTimeout time.Duration
	logger         Logger
}

// NewPublisher creates an outbox publisher.
func NewPublisher(store OutboxStore, producer Producer, batchSize int) *Publisher {
	return NewPublisherWithConfig(store, producer, PublisherConfig{BatchSize: batchSize})
}

// NewPublisherWithConfig creates an outbox publisher with explicit runtime settings.
func NewPublisherWithConfig(store OutboxStore, producer Producer, config PublisherConfig) *Publisher {
	batchSize := config.BatchSize
	if batchSize <= 0 {
		batchSize = 50
	}
	publishTimeout := config.PublishTimeout
	if publishTimeout <= 0 {
		publishTimeout = 10 * time.Second
	}
	logger := config.Logger
	if logger == nil {
		logger = log.Default()
	}
	return &Publisher{
		store:          store,
		producer:       producer,
		batchSize:      batchSize,
		publishTimeout: publishTimeout,
		logger:         logger,
	}
}

// PublishOnce claims and publishes one batch of pending outbox messages.
func (publisher *Publisher) PublishOnce(ctx context.Context) error {
	messages, err := publisher.store.ClaimPendingOutbox(ctx, publisher.batchSize)
	if err != nil || len(messages) == 0 {
		return err
	}
	kafkaMessages := make([]sharedkafka.Message, 0, len(messages))
	for _, message := range messages {
		kafkaMessages = append(kafkaMessages, sharedkafka.Message{
			Key:   []byte(message.PartitionKey),
			Value: message.Payload,
			Time:  message.CreatedAt,
		})
	}
	publishCtx, cancel := context.WithTimeout(ctx, publisher.publishTimeout)
	defer cancel()
	if err := publisher.producer.Publish(publishCtx, kafkaMessages); err != nil {
		for _, message := range messages {
			if markErr := publisher.store.MarkOutboxFailed(ctx, message.ID, err); markErr != nil {
				publisher.logger.Printf("mark outbox failed status update failed id=%s: %v", message.ID, markErr)
			}
		}
		return err
	}
	for _, message := range messages {
		if err := publisher.store.MarkOutboxPublished(ctx, message.ID); err != nil {
			publisher.logger.Printf("mark outbox published failed id=%s: %v", message.ID, err)
			return err
		}
	}
	return nil
}

// Run starts a polling publisher loop until the context is canceled.
func (publisher *Publisher) Run(ctx context.Context, interval time.Duration) {
	if interval <= 0 {
		interval = 2 * time.Second
	}
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	for {
		_ = publisher.PublishOnce(ctx)
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		}
	}
}
