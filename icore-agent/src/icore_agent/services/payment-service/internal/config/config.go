package config

import (
	"fmt"
	"os"
	"strings"
	"time"

	"icore-payment-service/internal/domain/catalog"
	"icore-payment-service/internal/infrastructure/wechatpay"
	"icore-services-lib-go/envconfig"
	httpserver "icore-services-lib-go/http/server"
)

// Config is the payment-service runtime configuration.
type Config struct {
	Addr                  string
	DatabaseURL           string
	DBMaxOpenConns        int
	DBMaxIdleConns        int
	DBConnMaxLifetime     time.Duration
	KafkaBrokers          []string
	KafkaTopic            string
	KafkaCheckTimeout     time.Duration
	LoggingServiceURL     string
	LoggingServiceToken   string
	LoggingServiceName    string
	LoggingServiceTimeout time.Duration
	LoggingQueueSize      int
	Catalog               catalog.Catalog
	WeChatPay             wechatpay.Config
	OrderTTL              time.Duration
	ReadHeaderTimeout     time.Duration
	ReadTimeout           time.Duration
	WriteTimeout          time.Duration
	IdleTimeout           time.Duration
	ShutdownTimeout       time.Duration
	OutboxPollInterval    time.Duration
	OutboxBatchSize       int
	OutboxPublishTimeout  time.Duration
	ReconcilePollInterval time.Duration
	ReconcileBatchSize    int
	ReconcileQueryTimeout time.Duration
}

// Load reads process environment and validates payment-owned configuration.
func Load() (Config, error) {
	catalogJSON, err := readRequiredFile("PAYMENT_CATALOG_JSON_PATH")
	if err != nil {
		return Config{}, err
	}
	cat, err := catalog.ParseJSON(catalogJSON)
	if err != nil {
		return Config{}, err
	}
	if err := cat.ValidateRequiredMonthlyPlans([]string{"pro", "team", "premium", "byok"}); err != nil {
		return Config{}, err
	}

	databaseURL := envconfig.String("PAYMENT_DATABASE_URL", "")
	if databaseURL == "" {
		return Config{}, fmt.Errorf("PAYMENT_DATABASE_URL is required")
	}

	return Config{
		Addr:                  envconfig.String("PAYMENT_SERVICE_ADDR", ":8080"),
		DatabaseURL:           databaseURL,
		DBMaxOpenConns:        envconfig.Int("PAYMENT_DB_MAX_OPEN_CONNS", 10),
		DBMaxIdleConns:        envconfig.Int("PAYMENT_DB_MAX_IDLE_CONNS", 5),
		DBConnMaxLifetime:     envconfig.Duration("PAYMENT_DB_CONN_MAX_LIFETIME", 30*time.Minute),
		KafkaBrokers:          envconfig.CSV("PAYMENT_KAFKA_BROKERS", "kafka:9092"),
		KafkaTopic:            envconfig.String("PAYMENT_KAFKA_TOPIC", "payment.events.v1"),
		KafkaCheckTimeout:     envconfig.Duration("PAYMENT_KAFKA_CHECK_TIMEOUT", 10*time.Second),
		LoggingServiceURL:     envconfig.String("LOGGING_SERVICE_URL", "http://logging-service:8091"),
		LoggingServiceToken:   envconfig.String("LOGGING_SERVICE_TOKEN", ""),
		LoggingServiceName:    envconfig.String("PAYMENT_LOGGING_SERVICE_NAME", "payment-service"),
		LoggingServiceTimeout: envconfig.Duration("PAYMENT_LOGGING_SERVICE_TIMEOUT", 2*time.Second),
		LoggingQueueSize:      envconfig.Int("PAYMENT_LOGGING_QUEUE_SIZE", 4096),
		Catalog:               cat,
		WeChatPay: wechatpay.Config{
			AppID:                    envconfig.String("WECHATPAY_APP_ID", ""),
			MchID:                    envconfig.String("WECHATPAY_MCH_ID", ""),
			MchCertificateSerialNo:   envconfig.String("WECHATPAY_MCH_CERT_SERIAL_NO", ""),
			MchPrivateKeyPath:        envconfig.String("WECHATPAY_MCH_PRIVATE_KEY_PATH", ""),
			APIv3Key:                 envconfig.String("WECHATPAY_API_V3_KEY", ""),
			PublicKeyID:              envconfig.String("WECHATPAY_PUBLIC_KEY_ID", ""),
			PublicKeyPath:            envconfig.String("WECHATPAY_PUBLIC_KEY_PATH", ""),
			NotifyURL:                envconfig.String("WECHATPAY_NOTIFY_URL", ""),
			APIHost:                  envconfig.String("WECHATPAY_API_HOST", ""),
			HTTPTimeout:              envconfig.Duration("WECHATPAY_HTTP_TIMEOUT", 10*time.Second),
			RequireProductionAPIHost: envconfig.Bool("WECHATPAY_REQUIRE_PRODUCTION_HOST", false),
		},
		OrderTTL:           envconfig.Duration("PAYMENT_ORDER_TTL", 30*time.Minute),
		ReadHeaderTimeout:  envconfig.Duration("PAYMENT_READ_HEADER_TIMEOUT", 5*time.Second),
		ReadTimeout:        envconfig.Duration("PAYMENT_READ_TIMEOUT", 30*time.Second),
		WriteTimeout:       envconfig.Duration("PAYMENT_WRITE_TIMEOUT", 30*time.Second),
		IdleTimeout:        envconfig.Duration("PAYMENT_IDLE_TIMEOUT", 60*time.Second),
		ShutdownTimeout:    envconfig.Duration("PAYMENT_SHUTDOWN_TIMEOUT", 10*time.Second),
		OutboxPollInterval: envconfig.Duration("PAYMENT_OUTBOX_POLL_INTERVAL", 2*time.Second),
		OutboxBatchSize:    envconfig.Int("PAYMENT_OUTBOX_BATCH_SIZE", 50),
		OutboxPublishTimeout: envconfig.Duration(
			"PAYMENT_OUTBOX_PUBLISH_TIMEOUT",
			10*time.Second,
		),
		ReconcilePollInterval: envconfig.Duration("PAYMENT_RECONCILIATION_POLL_INTERVAL", 30*time.Second),
		ReconcileBatchSize:    envconfig.Int("PAYMENT_RECONCILIATION_BATCH_SIZE", 50),
		ReconcileQueryTimeout: envconfig.Duration("PAYMENT_RECONCILIATION_QUERY_TIMEOUT", 10*time.Second),
	}, nil
}

// HTTPServerConfig returns the shared HTTP server configuration.
func (cfg Config) HTTPServerConfig() httpserver.Config {
	return httpserver.Config{
		Addr:              cfg.Addr,
		ReadHeaderTimeout: cfg.ReadHeaderTimeout,
		ReadTimeout:       cfg.ReadTimeout,
		WriteTimeout:      cfg.WriteTimeout,
		IdleTimeout:       cfg.IdleTimeout,
	}
}

func readRequiredFile(envName string) (string, error) {
	path := strings.TrimSpace(os.Getenv(envName))
	if path == "" {
		return "", fmt.Errorf("%s is required", envName)
	}
	content, err := os.ReadFile(path)
	if err != nil {
		return "", fmt.Errorf("read %s %q: %w", envName, path, err)
	}
	return string(content), nil
}
