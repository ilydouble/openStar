package pipeline

import (
	"encoding/json"
	"net"
	"net/http"
	"strings"
)

func getClientIP(r *http.Request) string {
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

func classifyUserAgentType(value string) string {
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

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}
