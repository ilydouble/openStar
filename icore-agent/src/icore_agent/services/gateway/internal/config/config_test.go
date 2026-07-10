package config

import (
	"reflect"
	"testing"
	"time"
)

// TestLoadReadsGatewayCORSOrigins verifies exact origins are loaded from CSV config.
func TestLoadReadsGatewayCORSOrigins(t *testing.T) {
	t.Setenv("GATEWAY_CORS_ALLOWED_ORIGINS", "https://app.example.com, https://admin.example.com")

	cfg := Load()

	want := []string{"https://app.example.com", "https://admin.example.com"}
	if !reflect.DeepEqual(cfg.CORSAllowedOrigins, want) {
		t.Fatalf("CORSAllowedOrigins = %#v, want %#v", cfg.CORSAllowedOrigins, want)
	}
}

// TestLoadAllowsGatewayCORSToBeDisabled verifies an explicit empty value disables CORS.
func TestLoadAllowsGatewayCORSToBeDisabled(t *testing.T) {
	t.Setenv("GATEWAY_CORS_ALLOWED_ORIGINS", "")

	cfg := Load()

	if len(cfg.CORSAllowedOrigins) != 0 {
		t.Fatalf("CORSAllowedOrigins = %#v, want empty", cfg.CORSAllowedOrigins)
	}
}

// TestTimeLocationResolvesGatewayTimeZone verifies gateway timestamps use the configured IANA zone.
func TestTimeLocationResolvesGatewayTimeZone(t *testing.T) {
	t.Setenv("GATEWAY_TIME_ZONE", "Asia/Shanghai")

	cfg := Load()
	location, err := cfg.TimeLocation()
	if err != nil {
		t.Fatalf("TimeLocation returned error: %v", err)
	}

	got := time.Date(2026, 5, 16, 7, 22, 52, 742470455, time.UTC).
		In(location).
		Format(time.RFC3339Nano)
	if got != "2026-05-16T15:22:52.742470455+08:00" {
		t.Fatalf("localized time = %q", got)
	}
}

// TestLoadReadsAccessLogQueueSize verifies access log buffering is configurable.
func TestLoadReadsAccessLogQueueSize(t *testing.T) {
	t.Setenv("GATEWAY_ACCESS_LOG_QUEUE_SIZE", "128")

	cfg := Load()

	if cfg.AccessLogQueueSize != 128 {
		t.Fatalf("AccessLogQueueSize = %d, want 128", cfg.AccessLogQueueSize)
	}
}

// TestLoadReadsGatewayRateLimitProfiles verifies token bucket profiles come from env.
func TestLoadReadsGatewayRateLimitProfiles(t *testing.T) {
	t.Setenv("GATEWAY_CLIENT_IP_RATE", "21")
	t.Setenv("GATEWAY_CLIENT_IP_BURST", "42")
	t.Setenv("GATEWAY_USER_ID_RATE", "11")
	t.Setenv("GATEWAY_USER_ID_BURST", "22")
	t.Setenv("ICORE_AGENT_RATE", "7")
	t.Setenv("ICORE_AGENT_BURST", "14")
	t.Setenv("PAYMENT_SERVICE_RATE", "3")
	t.Setenv("PAYMENT_SERVICE_BURST", "6")

	cfg := Load()

	if cfg.ClientIPRateLimit != (RateLimitProfile{RatePerSecond: 21, Burst: 42}) {
		t.Fatalf("ClientIPRateLimit = %#v", cfg.ClientIPRateLimit)
	}
	if cfg.UserIDRateLimit != (RateLimitProfile{RatePerSecond: 11, Burst: 22}) {
		t.Fatalf("UserIDRateLimit = %#v", cfg.UserIDRateLimit)
	}
	if cfg.ServiceRateLimitProfile("icore-agent") != (RateLimitProfile{RatePerSecond: 7, Burst: 14}) {
		t.Fatalf("service profile = %#v", cfg.ServiceRateLimitProfile("icore-agent"))
	}
	if cfg.ServiceRateLimitProfile("payment-service") != (RateLimitProfile{RatePerSecond: 3, Burst: 6}) {
		t.Fatalf("payment service profile = %#v", cfg.ServiceRateLimitProfile("payment-service"))
	}
}

func TestLoadReadsPaymentServiceURL(t *testing.T) {
	t.Setenv("GATEWAY_PAYMENT_SERVICE_URL", "http://payment.local")

	cfg := Load()

	if cfg.PaymentServiceURL != "http://payment.local" {
		t.Fatalf("PaymentServiceURL = %q", cfg.PaymentServiceURL)
	}
}

// TestServiceRateLimitEnvPrefixNormalizesServiceNames documents service env naming.
func TestServiceRateLimitEnvPrefixNormalizesServiceNames(t *testing.T) {
	if got := ServiceRateLimitEnvPrefix("icore-agent"); got != "ICORE_AGENT" {
		t.Fatalf("prefix = %q, want ICORE_AGENT", got)
	}
}
