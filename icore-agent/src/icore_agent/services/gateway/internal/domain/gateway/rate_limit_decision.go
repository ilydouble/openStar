package gateway

// RateLimitDecision is the normalized result returned by rate limit backends.
type RateLimitDecision struct {
	Allowed      bool
	Result       string
	RejectReason string
}
