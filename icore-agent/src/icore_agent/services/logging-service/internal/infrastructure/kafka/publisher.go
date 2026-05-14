package kafka

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"

	segmentio "github.com/segmentio/kafka-go"

	domain "xiehe-logging-service/internal/domain/logging"
)

// Publisher writes logging events to a Kafka topic using kafka-go.
type Publisher struct {
	brokers []string
	topic   string
	writer  *segmentio.Writer
}

// NewPublisher creates a Kafka publisher for the configured brokers and topic.
func NewPublisher(brokers []string, topic string) *Publisher {
	return &Publisher{
		brokers: brokers,
		topic:   topic,
		writer: &segmentio.Writer{
			Addr:         segmentio.TCP(brokers...),
			Topic:        topic,
			RequiredAcks: segmentio.RequireOne,
			Balancer:     &segmentio.Hash{},
			BatchTimeout: 100 * time.Millisecond,
		},
	}
}

// Check verifies that a broker is reachable and the configured topic is visible.
func (publisher *Publisher) Check(ctx context.Context) error {
	if len(publisher.brokers) == 0 {
		return errors.New("kafka brokers are required")
	}
	if strings.TrimSpace(publisher.topic) == "" {
		return errors.New("kafka topic is required")
	}

	var failures []string
	for _, broker := range publisher.brokers {
		broker = strings.TrimSpace(broker)
		if broker == "" {
			continue
		}

		conn, err := segmentio.DialContext(ctx, "tcp", broker)
		if err != nil {
			failures = append(failures, fmt.Sprintf("%s: %v", broker, err))
			continue
		}

		partitions, readErr := conn.ReadPartitions(publisher.topic)
		closeErr := conn.Close()
		if readErr != nil {
			failures = append(failures, fmt.Sprintf("%s topic %q: %v", broker, publisher.topic, readErr))
			continue
		}
		if closeErr != nil {
			failures = append(failures, fmt.Sprintf("%s close: %v", broker, closeErr))
			continue
		}
		if len(partitions) == 0 {
			failures = append(failures, fmt.Sprintf("%s topic %q has no partitions", broker, publisher.topic))
			continue
		}
		return nil
	}

	if len(failures) == 0 {
		return errors.New("kafka brokers are required")
	}
	return fmt.Errorf("kafka startup check failed for topic %q: %s", publisher.topic, strings.Join(failures, "; "))
}

// Publish serializes a batch of events and sends them as Kafka messages.
func (publisher *Publisher) Publish(ctx context.Context, events []domain.LogEvent) error {
	if len(events) == 0 {
		return nil
	}

	messages := make([]segmentio.Message, 0, len(events))
	for _, event := range events {
		payload, err := json.Marshal(event)
		if err != nil {
			return err
		}
		messages = append(messages, segmentio.Message{
			Key:   []byte(event.TraceID),
			Value: payload,
			Time:  event.Timestamp,
		})
	}
	return publisher.writer.WriteMessages(ctx, messages...)
}

// Close releases the underlying Kafka writer.
func (publisher *Publisher) Close() error {
	return publisher.writer.Close()
}
