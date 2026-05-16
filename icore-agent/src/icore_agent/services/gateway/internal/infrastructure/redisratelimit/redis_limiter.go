package redisratelimit

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/redis/go-redis/v9"
	domain "icore-gateway/internal/domain/gateway"
)

// RedisLimiter applies a fixed-window service-level limit through Redis counters.
type RedisLimiter struct {
	client    redis.UniversalClient
	limit     int
	window    time.Duration
	keyPrefix string
	now       func() time.Time
}

// NewRedisLimiter creates a Redis-backed fixed-window limiter.
func NewRedisLimiter(
	client redis.UniversalClient,
	limit int,
	window time.Duration,
	keyPrefix string,
	now func() time.Time,
) *RedisLimiter {
	if window <= 0 {
		window = time.Minute
	}
	if keyPrefix == "" {
		keyPrefix = "icore-gateway:rate"
	}
	if now == nil {
		now = time.Now
	}
	return &RedisLimiter{
		client:    client,
		limit:     limit,
		window:    window,
		keyPrefix: keyPrefix,
		now:       now,
	}
}

// Allow increments the service window counter and returns a normalized decision.
func (limiter *RedisLimiter) Allow(ctx context.Context, service string) (domain.RateLimitDecision, error) {
	if limiter.limit <= 0 {
		return domain.RateLimitDecision{Allowed: true, Result: "disabled"}, nil
	}
	windowSeconds := int64(limiter.window.Seconds())
	if windowSeconds <= 0 {
		windowSeconds = 60
	}
	windowID := limiter.now().Unix() / windowSeconds
	key := fmt.Sprintf("%s:%s:%d", limiter.keyPrefix, sanitizeRateKey(service), windowID)

	count, err := limiter.client.Incr(ctx, key).Result()
	if err != nil {
		return domain.RateLimitDecision{}, err
	}
	if count == 1 {
		if err := limiter.client.Expire(ctx, key, limiter.window).Err(); err != nil {
			return domain.RateLimitDecision{}, err
		}
	}
	if count > int64(limiter.limit) {
		return domain.RateLimitDecision{
			Allowed:      false,
			Result:       "rejected",
			RejectReason: "service rate limit exceeded",
		}, nil
	}
	return domain.RateLimitDecision{Allowed: true, Result: "allowed"}, nil
}

func sanitizeRateKey(value string) string {
	value = strings.TrimSpace(value)
	if value == "" {
		return "unknown"
	}
	replacer := strings.NewReplacer(":", "_", "/", "_", " ", "_")
	return replacer.Replace(value)
}
