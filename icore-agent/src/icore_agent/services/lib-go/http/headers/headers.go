package headers

import (
	"net"
	"net/http"
	"strings"
)

const (
	// HeaderXRequestID is the gateway request-correlation header.
	HeaderXRequestID = "X-Request-ID"
	// HeaderXUserID carries the trusted gateway-authenticated user id.
	HeaderXUserID = "X-User-ID"
	// HeaderXUserRoles carries trusted gateway-authenticated user roles.
	HeaderXUserRoles = "X-User-Roles"
	// HeaderXForwardedFor carries the original client IP chain.
	HeaderXForwardedFor = "X-Forwarded-For"
	// HeaderXRealIP carries the direct upstream client IP.
	HeaderXRealIP = "X-Real-IP"
)

// ClientIP extracts the best available caller IP from trusted gateway headers.
func ClientIP(r *http.Request) string {
	if forwardedFor := strings.TrimSpace(r.Header.Get(HeaderXForwardedFor)); forwardedFor != "" {
		parts := strings.Split(forwardedFor, ",")
		if len(parts) > 0 {
			return strings.TrimSpace(parts[0])
		}
	}
	if realIP := strings.TrimSpace(r.Header.Get(HeaderXRealIP)); realIP != "" {
		return realIP
	}
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err == nil {
		return host
	}
	return strings.TrimSpace(r.RemoteAddr)
}
