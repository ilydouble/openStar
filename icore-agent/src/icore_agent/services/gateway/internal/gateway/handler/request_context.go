package handler

import (
	"crypto/rand"
	"encoding/hex"
	"net"
	"net/http"
	"strings"
	"time"

	"icore-gateway/internal/gateway"
)

// beginRequest normalizes request identity and initializes gateway log metadata.
func (handler *Handler) beginRequest(w http.ResponseWriter, r *http.Request, upstream *string) (*gateway.GatewayMetadata, time.Time) {
	start := handler.now().In(handler.location)
	requestID := resolveRequestID(r.Header.Get(requestIDHeader))
	r.Header.Set(requestIDHeader, requestID)
	w.Header().Set(requestIDHeader, requestID)

	metadata := &gateway.GatewayMetadata{
		RequestTimestamp: start.Format(time.RFC3339Nano),
		RequestID:        requestID,
		Method:           r.Method,
		Path:             r.URL.Path,
		Query:            r.URL.RawQuery,
		ClientIP:         clientIP(r),
		AuthResult:       "skipped",
		UserAgent:        classifyUserAgent(r.UserAgent()),
		Roles:            []string{},
		UpstreamService:  upstream,
		RateLimitResult:  "skipped",
	}
	if upstream != nil {
		addr := handler.backend.String()
		metadata.UpstreamAddr = &addr
	}
	return metadata, start
}

// resolveRequestID reuses a safe inbound request id or generates a new one.
func resolveRequestID(value string) string {
	if normalized := strings.TrimSpace(value); normalized != "" && !strings.ContainsAny(normalized, "\r\n") {
		return normalized
	}
	raw := make([]byte, 16)
	if _, err := rand.Read(raw); err != nil {
		return time.Now().Format("20060102150405.000000000")
	}
	return hex.EncodeToString(raw)
}

// clientIP resolves the original caller IP from forwarded headers or RemoteAddr.
func clientIP(r *http.Request) string {
	if forwardedFor := strings.TrimSpace(r.Header.Get("X-Forwarded-For")); forwardedFor != "" {
		return strings.TrimSpace(strings.Split(forwardedFor, ",")[0])
	}
	if realIP := strings.TrimSpace(r.Header.Get("X-Real-IP")); realIP != "" {
		return realIP
	}
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		return r.RemoteAddr
	}
	return host
}

// classifyUserAgent normalizes the caller family for gateway metadata.
func classifyUserAgent(value string) string {
	lower := strings.ToLower(value)
	switch {
	case lower == "":
		return "unknown"
	case strings.Contains(lower, "bot") || strings.Contains(lower, "spider") || strings.Contains(lower, "crawler"):
		return "crawler"
	case strings.Contains(lower, "postman") || strings.Contains(lower, "insomnia") || strings.Contains(lower, "apifox"):
		return "api_testing_tool"
	case strings.Contains(lower, "curl") || strings.Contains(lower, "wget") || strings.Contains(lower, "python-requests") || strings.Contains(lower, "httpie"):
		return "script"
	case strings.Contains(lower, "mobile") || strings.Contains(lower, "okhttp") || strings.Contains(lower, "cfnetwork"):
		return "mobile_app"
	case strings.Contains(lower, "mozilla") || strings.Contains(lower, "chrome") || strings.Contains(lower, "safari") || strings.Contains(lower, "firefox"):
		return "browser"
	default:
		return "unknown"
	}
}
