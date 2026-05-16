package gateway

import (
	"crypto/rand"
	"encoding/hex"
	"strings"
	"time"
)

const (
	// RequestIDHeader is the canonical gateway request-correlation header.
	RequestIDHeader = "X-Request-ID"
)

// RequestIDPolicy normalizes inbound request ids and generates safe fallback ids.
type RequestIDPolicy struct {
	Generate func() string
}

// Resolve returns a safe request id for the current request.
func (policy RequestIDPolicy) Resolve(value string) string {
	if normalized := strings.TrimSpace(value); normalized != "" && !strings.ContainsAny(normalized, "\r\n") {
		return normalized
	}
	if policy.Generate != nil {
		return policy.Generate()
	}
	return generateRequestID()
}

func generateRequestID() string {
	raw := make([]byte, 16)
	if _, err := rand.Read(raw); err != nil {
		return time.Now().Format("20060102150405.000000000")
	}
	return hex.EncodeToString(raw)
}
