package redisratelimit

import (
	"context"
	"testing"
	"time"
)

func TestRedisLimiterDisabledWhenLimitIsZero(t *testing.T) {
	limiter := NewRedisLimiter(nil, 0, time.Minute, "", time.Now)

	decision, err := limiter.Allow(context.Background(), "icore-agent")
	if err != nil {
		t.Fatalf("allow: %v", err)
	}
	if !decision.Allowed || decision.Result != "disabled" {
		t.Fatalf("decision = %#v, want disabled allow", decision)
	}
}
