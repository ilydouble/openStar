package kafka

import (
	"bytes"
	"context"
	"errors"
	"log"
	"strings"
	"testing"
	"time"

	postgresrepo "icore-payment-service/internal/infrastructure/persistence/postgres"
	sharedkafka "icore-services-lib-go/mq/kafka"
)

type fakeOutboxStore struct {
	messages     []postgresrepo.OutboxMessage
	publishedIDs []string
	failedIDs    []string
	publishedErr error
	failedErr    error
}

func (store *fakeOutboxStore) ClaimPendingOutbox(_ context.Context, _ int) ([]postgresrepo.OutboxMessage, error) {
	return store.messages, nil
}

func (store *fakeOutboxStore) MarkOutboxPublished(_ context.Context, id string) error {
	store.publishedIDs = append(store.publishedIDs, id)
	return store.publishedErr
}

func (store *fakeOutboxStore) MarkOutboxFailed(_ context.Context, id string, _ error) error {
	store.failedIDs = append(store.failedIDs, id)
	return store.failedErr
}

type fakeProducer struct {
	err      error
	block    bool
	messages []sharedkafka.Message
}

func (producer *fakeProducer) Publish(ctx context.Context, messages []sharedkafka.Message) error {
	producer.messages = append([]sharedkafka.Message(nil), messages...)
	if producer.block {
		<-ctx.Done()
		return ctx.Err()
	}
	return producer.err
}

func TestPublishOnceUsesPerBatchTimeoutAndMarksFailed(t *testing.T) {
	store := &fakeOutboxStore{messages: []postgresrepo.OutboxMessage{outboxMessage("event-1")}}
	producer := &fakeProducer{block: true}
	var logs bytes.Buffer
	publisher := NewPublisherWithConfig(store, producer, PublisherConfig{
		BatchSize:      1,
		PublishTimeout: 10 * time.Millisecond,
		Logger:         log.New(&logs, "", 0),
	})

	start := time.Now()
	err := publisher.PublishOnce(context.Background())

	if !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("PublishOnce error = %v, want context deadline exceeded", err)
	}
	if elapsed := time.Since(start); elapsed > time.Second {
		t.Fatalf("PublishOnce elapsed = %s, want bounded timeout", elapsed)
	}
	if len(store.failedIDs) != 1 || store.failedIDs[0] != "event-1" {
		t.Fatalf("failed ids = %#v, want event-1", store.failedIDs)
	}
}

func TestPublishOnceLogsMarkPublishedFailure(t *testing.T) {
	store := &fakeOutboxStore{
		messages:     []postgresrepo.OutboxMessage{outboxMessage("event-1")},
		publishedErr: errors.New("database unavailable"),
	}
	producer := &fakeProducer{}
	var logs bytes.Buffer
	publisher := NewPublisherWithConfig(store, producer, PublisherConfig{
		Logger: log.New(&logs, "", 0),
	})

	err := publisher.PublishOnce(context.Background())

	if err == nil || !strings.Contains(err.Error(), "database unavailable") {
		t.Fatalf("PublishOnce error = %v, want mark published error", err)
	}
	if !strings.Contains(logs.String(), "mark outbox published failed") {
		t.Fatalf("logs = %q, want mark published failure", logs.String())
	}
}

func TestPublishOnceLogsMarkFailedFailure(t *testing.T) {
	store := &fakeOutboxStore{
		messages:  []postgresrepo.OutboxMessage{outboxMessage("event-1")},
		failedErr: errors.New("database unavailable"),
	}
	producer := &fakeProducer{err: errors.New("kafka unavailable")}
	var logs bytes.Buffer
	publisher := NewPublisherWithConfig(store, producer, PublisherConfig{
		Logger: log.New(&logs, "", 0),
	})

	err := publisher.PublishOnce(context.Background())

	if err == nil || !strings.Contains(err.Error(), "kafka unavailable") {
		t.Fatalf("PublishOnce error = %v, want publish error", err)
	}
	if !strings.Contains(logs.String(), "mark outbox failed status update failed") {
		t.Fatalf("logs = %q, want mark failed update failure", logs.String())
	}
}

func outboxMessage(id string) postgresrepo.OutboxMessage {
	return postgresrepo.OutboxMessage{
		ID:           id,
		EventType:    "payment.order.succeeded",
		PartitionKey: "user-1",
		Payload:      []byte(`{"event_id":"` + id + `"}`),
		CreatedAt:    time.Date(2026, 6, 6, 10, 0, 0, 0, time.UTC),
	}
}
