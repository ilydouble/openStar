package config

import (
	"testing"
	"time"
)

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
