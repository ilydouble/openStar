package handler

import (
	"context"
	"log"

	"icore-gateway/internal/gateway"
)

// allowRequest applies service-level limits and records the normalized decision.
func (handler *Handler) allowRequest(ctx context.Context, metadata *gateway.GatewayMetadata, service string) bool {
	if handler.limiter == nil {
		metadata.RateLimitResult = "skipped"
		return true
	}

	decision, err := handler.limiter.Allow(ctx, service)
	if err != nil {
		metadata.RateLimitResult = "error"
		errorType := "rate_limit_error"
		metadata.ErrorType = &errorType
		log.Printf("gateway rate limit check failed: %v", err)
		return true
	}
	metadata.RateLimitResult = decision.Result
	if decision.Result == "" {
		metadata.RateLimitResult = "allowed"
	}
	if decision.Allowed {
		return true
	}

	reason := decision.RejectReason
	if reason == "" {
		reason = "service rate limit exceeded"
	}
	metadata.RejectReason = &reason
	return false
}
