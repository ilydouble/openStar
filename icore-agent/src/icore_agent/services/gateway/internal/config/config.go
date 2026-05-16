package config

import (
	"strings"
	"time"
	_ "time/tzdata"

	"icore-services-lib-go/envconfig"
	httpserver "icore-services-lib-go/http/server"
)

// Config is the environment-derived runtime configuration for icore-gateway.
type Config struct {
	Addr                  string
	BackendURL            string
	LoggingServiceName    string
	LoggingServiceURL     string
	LoggingServiceToken   string
	LoggingServiceTimeout time.Duration
	AccessLogQueueSize    int
	RedisURL              string
	JWTSecret             string
	JWTIssuer             string
	JWTAudience           string
	TimeZone              string
	RateLimitWindow       time.Duration
	RateLimitWindowLimit  int
	RateLimitKeyPrefix    string
	ReadHeaderTimeout     time.Duration
	ReadTimeout           time.Duration
	WriteTimeout          time.Duration
	IdleTimeout           time.Duration
	ShutdownTimeout       time.Duration
}

// Load reads environment variables and applies local development defaults.
func Load() Config {
	return Config{
		Addr:                  envconfig.String("GATEWAY_ADDR", ":11000"),
		BackendURL:            envconfig.String("GATEWAY_BACKEND_URL", "http://icore-agent:11001"),
		LoggingServiceName:    envconfig.String("GATEWAY_LOGGING_SERVICE_NAME", "icore-gateway"),
		LoggingServiceURL:     envconfig.String("LOGGING_SERVICE_URL", "http://logging-service:8091"),
		LoggingServiceToken:   envconfig.String("LOGGING_SERVICE_TOKEN", "dev-logging-service-token"),
		LoggingServiceTimeout: envconfig.Duration("GATEWAY_LOGGING_SERVICE_TIMEOUT", 2*time.Second),
		AccessLogQueueSize:    envconfig.Int("GATEWAY_ACCESS_LOG_QUEUE_SIZE", 4096),
		RedisURL:              envconfig.String("REDIS_URL", "redis://redis:6379/0"),
		JWTSecret:             envconfig.String("JWT_SECRET", "dev-icore-jwt-secret-change-me-32-bytes"),
		JWTIssuer:             envconfig.String("JWT_ISSUER", "icore-agent"),
		JWTAudience:           envconfig.String("JWT_AUDIENCE", "icore-gateway"),
		TimeZone:              envconfig.String("GATEWAY_TIME_ZONE", "Asia/Shanghai"),
		RateLimitWindow:       envconfig.Duration("GATEWAY_RATE_LIMIT_WINDOW", time.Minute),
		RateLimitWindowLimit:  envconfig.Int("GATEWAY_RATE_LIMIT_WINDOW_LIMIT", 600),
		RateLimitKeyPrefix:    envconfig.String("GATEWAY_RATE_LIMIT_KEY_PREFIX", "icore-gateway:rate"),
		ReadHeaderTimeout:     envconfig.Duration("GATEWAY_READ_HEADER_TIMEOUT", 5*time.Second),
		ReadTimeout:           envconfig.Duration("GATEWAY_READ_TIMEOUT", 30*time.Second),
		WriteTimeout:          envconfig.Duration("GATEWAY_WRITE_TIMEOUT", 120*time.Second),
		IdleTimeout:           envconfig.Duration("GATEWAY_IDLE_TIMEOUT", 60*time.Second),
		ShutdownTimeout:       envconfig.Duration("GATEWAY_SHUTDOWN_TIMEOUT", 10*time.Second),
	}
}

// TimeLocation resolves the configured IANA time zone used for gateway log timestamps.
func (cfg Config) TimeLocation() (*time.Location, error) {
	name := strings.TrimSpace(cfg.TimeZone)
	if name == "" || strings.EqualFold(name, "local") {
		return time.Local, nil
	}
	if strings.EqualFold(name, "utc") {
		return time.UTC, nil
	}
	return time.LoadLocation(name)
}

// HTTPServerConfig returns the shared HTTP server settings for the gateway.
func (cfg Config) HTTPServerConfig() httpserver.Config {
	return httpserver.Config{
		Addr:              cfg.Addr,
		ReadHeaderTimeout: cfg.ReadHeaderTimeout,
		ReadTimeout:       cfg.ReadTimeout,
		WriteTimeout:      cfg.WriteTimeout,
		IdleTimeout:       cfg.IdleTimeout,
	}
}
