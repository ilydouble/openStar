package config

import (
	"strings"
	"time"
	_ "time/tzdata"
	"unicode"

	"icore-services-lib-go/envconfig"
	httpserver "icore-services-lib-go/http/server"
)

// Config is the environment-derived runtime configuration for icore-gateway.
type Config struct {
	Addr                  string
	BackendURL            string
	PaymentServiceURL     string
	CORSAllowedOrigins    []string
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
	RateLimitKeyPrefix    string
	ClientIPRateLimit     RateLimitProfile
	UserIDRateLimit       RateLimitProfile
	ServiceRateLimits     map[string]RateLimitProfile
	ReadHeaderTimeout     time.Duration
	ReadTimeout           time.Duration
	WriteTimeout          time.Duration
	IdleTimeout           time.Duration
	ShutdownTimeout       time.Duration
}

// RateLimitProfile configures one token bucket rate limiter.
type RateLimitProfile struct {
	RatePerSecond int
	Burst         int
}

// Load reads environment variables and applies local development defaults.
func Load() Config {
	serviceRateLimits := map[string]RateLimitProfile{
		"icore-agent":     serviceRateLimitProfile("icore-agent", RateLimitProfile{RatePerSecond: 10, Burst: 20}),
		"payment-service": serviceRateLimitProfile("payment-service", RateLimitProfile{RatePerSecond: 5, Burst: 10}),
	}
	return Config{
		Addr:                  envconfig.String("GATEWAY_ADDR", ":11000"),
		BackendURL:            envconfig.String("GATEWAY_BACKEND_URL", "http://icore-agent:11001"),
		PaymentServiceURL:     envconfig.String("GATEWAY_PAYMENT_SERVICE_URL", "http://payment-service:8080"),
		CORSAllowedOrigins:    envconfig.CSVAllowEmpty("GATEWAY_CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000"),
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
		RateLimitKeyPrefix:    envconfig.String("GATEWAY_RATE_LIMIT_KEY_PREFIX", "icore-gateway:rate"),
		ClientIPRateLimit: RateLimitProfile{
			RatePerSecond: envconfig.Int("GATEWAY_CLIENT_IP_RATE", 20),
			Burst:         envconfig.Int("GATEWAY_CLIENT_IP_BURST", 40),
		},
		UserIDRateLimit: RateLimitProfile{
			RatePerSecond: envconfig.Int("GATEWAY_USER_ID_RATE", 10),
			Burst:         envconfig.Int("GATEWAY_USER_ID_BURST", 20),
		},
		ServiceRateLimits: serviceRateLimits,
		ReadHeaderTimeout: envconfig.Duration("GATEWAY_READ_HEADER_TIMEOUT", 5*time.Second),
		ReadTimeout:       envconfig.Duration("GATEWAY_READ_TIMEOUT", 30*time.Second),
		WriteTimeout:      envconfig.Duration("GATEWAY_WRITE_TIMEOUT", 120*time.Second),
		IdleTimeout:       envconfig.Duration("GATEWAY_IDLE_TIMEOUT", 60*time.Second),
		ShutdownTimeout:   envconfig.Duration("GATEWAY_SHUTDOWN_TIMEOUT", 10*time.Second),
	}
}

// ServiceRateLimitProfile returns the token bucket profile for one upstream service.
func (cfg Config) ServiceRateLimitProfile(service string) RateLimitProfile {
	if cfg.ServiceRateLimits == nil {
		return RateLimitProfile{}
	}
	return cfg.ServiceRateLimits[service]
}

// ServiceRateLimitEnvPrefix normalizes an upstream service name to its env prefix.
func ServiceRateLimitEnvPrefix(service string) string {
	service = strings.TrimSpace(service)
	var builder strings.Builder
	previousUnderscore := false
	for _, char := range service {
		if unicode.IsLetter(char) || unicode.IsDigit(char) {
			builder.WriteRune(unicode.ToUpper(char))
			previousUnderscore = false
			continue
		}
		if builder.Len() > 0 && !previousUnderscore {
			builder.WriteByte('_')
			previousUnderscore = true
		}
	}
	return strings.Trim(builder.String(), "_")
}

func serviceRateLimitProfile(service string, fallback RateLimitProfile) RateLimitProfile {
	prefix := ServiceRateLimitEnvPrefix(service)
	return RateLimitProfile{
		RatePerSecond: envconfig.Int(prefix+"_RATE", fallback.RatePerSecond),
		Burst:         envconfig.Int(prefix+"_BURST", fallback.Burst),
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
