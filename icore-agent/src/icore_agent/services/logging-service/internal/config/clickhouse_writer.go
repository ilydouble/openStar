package config

import (
	"fmt"
	"time"

	"icore-services-lib-go/envconfig"
)

// ClickHouseWriterConfig is the environment-derived config for the Kafka consumer.
type ClickHouseWriterConfig struct {
	KafkaBrokers       []string
	KafkaTopic         string
	KafkaGroupID       string
	ClickHouseHTTPURL  string
	ClickHouseDatabase string
	ClickHouseTable    string
	ClickHouseUser     string
	ClickHousePassword string
	BatchSize          int
	FlushInterval      time.Duration
	HTTPTimeout        time.Duration
}

// LoadClickHouseWriter reads Kafka and ClickHouse settings for clickhouse-writer.
func LoadClickHouseWriter() ClickHouseWriterConfig {
	host := envconfig.String("CLICKHOUSE_HOST", "clickhouse")
	httpPort := envconfig.String("CLICKHOUSE_HTTP_PORT", "8123")
	return ClickHouseWriterConfig{
		KafkaBrokers:       envconfig.CSV("LOGGING_KAFKA_BROKERS", "kafka:9092"),
		KafkaTopic:         envconfig.String("LOGGING_KAFKA_TOPIC", "logging.events.v1"),
		KafkaGroupID:       envconfig.String("CLICKHOUSE_WRITER_GROUP_ID", "logging-clickhouse-writer"),
		ClickHouseHTTPURL:  envconfig.String("CLICKHOUSE_HTTP_URL", fmt.Sprintf("http://%s:%s", host, httpPort)),
		ClickHouseDatabase: envconfig.String("CLICKHOUSE_DATABASE", "icore_logging_db"),
		ClickHouseTable:    envconfig.String("CLICKHOUSE_LOGS_TABLE", "icore_logs"),
		ClickHouseUser:     envconfig.String("CLICKHOUSE_USER", "icore_logging"),
		ClickHousePassword: envconfig.String("CLICKHOUSE_PASSWORD", ""),
		BatchSize:          envconfig.Int("CLICKHOUSE_WRITER_BATCH_SIZE", 500),
		FlushInterval:      envconfig.Duration("CLICKHOUSE_WRITER_FLUSH_INTERVAL", time.Second),
		HTTPTimeout:        envconfig.Duration("CLICKHOUSE_WRITER_HTTP_TIMEOUT", 5*time.Second),
	}
}
