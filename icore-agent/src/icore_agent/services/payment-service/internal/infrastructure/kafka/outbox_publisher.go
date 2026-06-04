package kafka

import (
	"context"
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

// Publisher sends transactional outbox messages to Kafka.
type Publisher struct {
	store     OutboxStore
	producer  *sharedkafka.KafkaPublisher
	batchSize int
}

// NewPublisher creates an outbox publisher.
func NewPublisher(store OutboxStore, producer *sharedkafka.KafkaPublisher, batchSize int) *Publisher {
	if batchSize <= 0 {
		batchSize = 50
	}
	return &Publisher{store: store, producer: producer, batchSize: batchSize}
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
	if err := publisher.producer.Publish(ctx, kafkaMessages); err != nil {
		for _, message := range messages {
			_ = publisher.store.MarkOutboxFailed(ctx, message.ID, err)
		}
		return err
	}
	for _, message := range messages {
		if err := publisher.store.MarkOutboxPublished(ctx, message.ID); err != nil {
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
