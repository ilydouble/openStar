package gateway

import (
	"context"
	"net/http"
	"time"

	sharedlogging "icore-services-lib-go/logging"
)

const (
	// AuthResultPublic marks routes that do not require bearer authentication.
	AuthResultPublic = "public"
	// AuthResultSuccess marks requests with a valid gateway JWT.
	AuthResultSuccess = "success"
	// AuthResultMissingToken marks protected requests without a bearer token.
	AuthResultMissingToken = "missing_token"
	// AuthResultInvalidToken marks protected requests with an invalid bearer token.
	AuthResultInvalidToken = "invalid_token"
)

// Config contains the runtime behavior for the gateway HTTP router.
type Config struct {
	BackendURL           string
	JWTSecret            string
	JWTIssuer            string
	JWTAudience          string
	LoggingServiceName   string
	RateLimitWindowLimit int
	TimeLocation         *time.Location
}

// Dependencies provides side-effecting gateway collaborators for tests and main.
type Dependencies struct {
	Logger    sharedlogging.Emitter
	Limiter   RateLimiter
	Transport http.RoundTripper
	Now       func() time.Time
}

// RateLimiter decides whether a request may enter an upstream service.
type RateLimiter interface {
	Allow(context.Context, string) (RateLimitDecision, error)
}

// RateLimitDecision is the normalized result returned by rate limit backends.
type RateLimitDecision struct {
	Allowed      bool
	Result       string
	RejectReason string
}

// GatewayMetadata is the metadata object stored under logging-service metadata.
type GatewayMetadata struct {
	RequestTimestamp   string   `json:"request_timestamp"`
	RequestID          string   `json:"request_id"`
	Method             string   `json:"method"`
	Path               string   `json:"path"`
	Query              string   `json:"query"`
	ClientIP           string   `json:"client_ip"`
	AuthResult         string   `json:"auth_result"`
	UserAgent          string   `json:"user_agent"`
	UserID             string   `json:"user_id"`
	Roles              []string `json:"roles"`
	UpstreamService    *string  `json:"upstream_service"`
	UpstreamAddr       *string  `json:"upstream_addr"`
	UpstreamStatusCode *int     `json:"upstream_status_code"`
	FinalStatusCode    int      `json:"final_status_code"`
	RequestElapsedTime int64    `json:"request_elapsed_time"`
	ErrorType          *string  `json:"error_type"`
	RateLimitResult    string   `json:"rate_limit_result"`
	RejectReason       *string  `json:"reject_reason"`
}
