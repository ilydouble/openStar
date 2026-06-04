package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"

	"icore-payment-service/internal/domain/catalog"
	"icore-payment-service/internal/infrastructure/wechatpay"
	httpserver "icore-services-lib-go/http/server"
)

// Config is the payment-service runtime configuration.
type Config struct {
	Addr               string
	DatabaseURL        string
	DBMaxOpenConns     int
	DBMaxIdleConns     int
	DBConnMaxLifetime  time.Duration
	KafkaBrokers       []string
	KafkaTopic         string
	Catalog            catalog.Catalog
	WeChatPay          wechatpay.Config
	OrderTTL           time.Duration
	ReadHeaderTimeout  time.Duration
	ReadTimeout        time.Duration
	WriteTimeout       time.Duration
	IdleTimeout        time.Duration
	ShutdownTimeout    time.Duration
	OutboxPollInterval time.Duration
	OutboxBatchSize    int
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

	databaseURL := strings.TrimSpace(os.Getenv("PAYMENT_DATABASE_URL"))
	if databaseURL == "" {
		return Config{}, fmt.Errorf("PAYMENT_DATABASE_URL is required")
	}

	return Config{
		Addr:              envString("PAYMENT_SERVICE_ADDR", ":8080"),
		DatabaseURL:       databaseURL,
		DBMaxOpenConns:    envInt("PAYMENT_DB_MAX_OPEN_CONNS", 10),
		DBMaxIdleConns:    envInt("PAYMENT_DB_MAX_IDLE_CONNS", 5),
		DBConnMaxLifetime: envDuration("PAYMENT_DB_CONN_MAX_LIFETIME", 30*time.Minute),
		KafkaBrokers:      envCSV("PAYMENT_KAFKA_BROKERS", "kafka:9092"),
		KafkaTopic:        envString("PAYMENT_KAFKA_TOPIC", "payment.events.v1"),
		Catalog:           cat,
		WeChatPay: wechatpay.Config{
			AppID:                    envString("WECHATPAY_APP_ID", ""),
			MchID:                    envString("WECHATPAY_MCH_ID", ""),
			MchCertificateSerialNo:   envString("WECHATPAY_MCH_CERT_SERIAL_NO", ""),
			MchPrivateKeyPath:        envString("WECHATPAY_MCH_PRIVATE_KEY_PATH", ""),
			APIv3Key:                 envString("WECHATPAY_API_V3_KEY", ""),
			PublicKeyID:              envString("WECHATPAY_PUBLIC_KEY_ID", ""),
			PublicKeyPath:            envString("WECHATPAY_PUBLIC_KEY_PATH", ""),
			NotifyURL:                envString("WECHATPAY_NOTIFY_URL", ""),
			APIHost:                  envString("WECHATPAY_API_HOST", ""),
			HTTPTimeout:              envDuration("WECHATPAY_HTTP_TIMEOUT", 10*time.Second),
			RequireProductionAPIHost: envBool("WECHATPAY_REQUIRE_PRODUCTION_HOST", false),
		},
		OrderTTL:           envDuration("PAYMENT_ORDER_TTL", 30*time.Minute),
		ReadHeaderTimeout:  envDuration("PAYMENT_READ_HEADER_TIMEOUT", 5*time.Second),
		ReadTimeout:        envDuration("PAYMENT_READ_TIMEOUT", 30*time.Second),
		WriteTimeout:       envDuration("PAYMENT_WRITE_TIMEOUT", 30*time.Second),
		IdleTimeout:        envDuration("PAYMENT_IDLE_TIMEOUT", 60*time.Second),
		ShutdownTimeout:    envDuration("PAYMENT_SHUTDOWN_TIMEOUT", 10*time.Second),
		OutboxPollInterval: envDuration("PAYMENT_OUTBOX_POLL_INTERVAL", 2*time.Second),
		OutboxBatchSize:    envInt("PAYMENT_OUTBOX_BATCH_SIZE", 50),
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

func envString(name string, fallback string) string {
	value := strings.TrimSpace(os.Getenv(name))
	if value == "" {
		return fallback
	}
	return value
}

func envCSV(name string, fallback string) []string {
	raw := envString(name, fallback)
	parts := strings.Split(raw, ",")
	values := make([]string, 0, len(parts))
	for _, part := range parts {
		part = strings.TrimSpace(part)
		if part != "" {
			values = append(values, part)
		}
	}
	return values
}

func envDuration(name string, fallback time.Duration) time.Duration {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return fallback
	}
	value, err := time.ParseDuration(raw)
	if err != nil {
		return fallback
	}
	return value
}

func envInt(name string, fallback int) int {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return fallback
	}
	value, err := strconv.Atoi(raw)
	if err != nil {
		return fallback
	}
	return value
}

func envBool(name string, fallback bool) bool {
	raw := strings.TrimSpace(os.Getenv(name))
	if raw == "" {
		return fallback
	}
	value, err := strconv.ParseBool(raw)
	if err != nil {
		return fallback
	}
	return value
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
