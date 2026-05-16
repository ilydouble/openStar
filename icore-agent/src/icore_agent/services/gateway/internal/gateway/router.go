package gateway

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"log"
	"net"
	"net/http"
	"net/http/httputil"
	"net/url"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"
)

const requestIDHeader = "X-Request-ID"

type gateway struct {
	cfg       Config
	logger    Logger
	limiter   RateLimiter
	transport http.RoundTripper
	now       func() time.Time
	location  *time.Location
	backend   *url.URL
	proxy     *httputil.ReverseProxy
}

type identity struct {
	userID string
	roles  []string
}

// NewRouter builds the chi gateway router with health, auth, limit, proxy, and logging.
func NewRouter(cfg Config, deps Dependencies) http.Handler {
	if cfg.LoggingServiceName == "" {
		cfg.LoggingServiceName = "icore-gateway"
	}
	now := deps.Now
	if now == nil {
		now = time.Now
	}
	location := cfg.TimeLocation
	if location == nil {
		location = time.Local
	}
	backend, err := url.Parse(cfg.BackendURL)
	if err != nil {
		panic(err)
	}

	gw := &gateway{
		cfg:       cfg,
		logger:    deps.Logger,
		limiter:   deps.Limiter,
		transport: deps.Transport,
		now:       now,
		location:  location,
		backend:   backend,
	}
	gw.proxy = gw.newProxy()

	router := chi.NewRouter()
	router.Get("/health", gw.handleHealth)
	router.Handle("/*", http.HandlerFunc(gw.handleProxy))
	return router
}

func (gw *gateway) handleHealth(w http.ResponseWriter, r *http.Request) {
	metadata, start := gw.beginRequest(w, r, nil)
	recorder := newStatusRecorder(w)
	defer gw.emitLog(r.Context(), start, metadata, recorder)

	metadata.AuthResult = AuthResultPublic
	metadata.RateLimitResult = "skipped"
	writeJSON(recorder, http.StatusOK, map[string]string{"status": "ok", "service": gw.cfg.LoggingServiceName})
}

func (gw *gateway) handleProxy(w http.ResponseWriter, r *http.Request) {
	upstream := "icore-agent"
	metadata, start := gw.beginRequest(w, r, &upstream)
	recorder := newStatusRecorder(w)
	defer gw.emitLog(r.Context(), start, metadata, recorder)

	ident, ok := gw.authenticate(r, metadata)
	if !ok {
		writeJSON(recorder, http.StatusUnauthorized, map[string]string{"message": "unauthorized"})
		return
	}
	if ident != nil {
		r.Header.Set("X-User-ID", ident.userID)
		r.Header.Set("X-User-Roles", strings.Join(ident.roles, ","))
	}

	if !gw.allowRequest(r.Context(), metadata, upstream) {
		writeJSON(recorder, http.StatusTooManyRequests, map[string]string{"message": "rate limit exceeded"})
		return
	}

	gw.proxy.ServeHTTP(recorder, r)
	if recorder.status != 0 {
		status := recorder.status
		metadata.UpstreamStatusCode = &status
	}
}

func (gw *gateway) beginRequest(w http.ResponseWriter, r *http.Request, upstream *string) (*GatewayMetadata, time.Time) {
	start := gw.now().In(gw.location)
	requestID := resolveRequestID(r.Header.Get(requestIDHeader))
	r.Header.Set(requestIDHeader, requestID)
	w.Header().Set(requestIDHeader, requestID)

	metadata := &GatewayMetadata{
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
		addr := gw.backend.String()
		metadata.UpstreamAddr = &addr
	}
	return metadata, start
}

func (gw *gateway) authenticate(r *http.Request, metadata *GatewayMetadata) (*identity, bool) {
	if isPublicPath(r.URL.Path) {
		metadata.AuthResult = AuthResultPublic
		return nil, true
	}

	raw := strings.TrimSpace(r.Header.Get("Authorization"))
	if !strings.HasPrefix(raw, "Bearer ") {
		metadata.AuthResult = AuthResultMissingToken
		reason := "missing bearer token"
		metadata.RejectReason = &reason
		return nil, false
	}

	claims, err := ValidateJWT(strings.TrimSpace(strings.TrimPrefix(raw, "Bearer ")), gw.cfg, gw.now())
	if err != nil {
		metadata.AuthResult = AuthResultInvalidToken
		reason := "invalid bearer token"
		metadata.RejectReason = &reason
		errorType := "auth_error"
		metadata.ErrorType = &errorType
		return nil, false
	}

	metadata.AuthResult = AuthResultSuccess
	metadata.UserID = claims.Subject
	metadata.Roles = claims.Roles
	return &identity{userID: claims.Subject, roles: claims.Roles}, true
}

func (gw *gateway) allowRequest(ctx context.Context, metadata *GatewayMetadata, service string) bool {
	if gw.limiter == nil {
		metadata.RateLimitResult = "skipped"
		return true
	}

	decision, err := gw.limiter.Allow(ctx, service)
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

func (gw *gateway) emitLog(ctx context.Context, start time.Time, metadata *GatewayMetadata, recorder *statusRecorder) {
	metadata.FinalStatusCode = recorder.Status()
	metadata.RequestElapsedTime = gw.now().Sub(start).Milliseconds()
	if metadata.FinalStatusCode >= http.StatusInternalServerError {
		errorType := "upstream_error"
		metadata.ErrorType = &errorType
	}
	if gw.logger == nil {
		return
	}

	level := LogLevelInfo
	if metadata.FinalStatusCode >= http.StatusInternalServerError {
		level = LogLevelError
	} else if metadata.FinalStatusCode >= http.StatusBadRequest {
		level = LogLevelWarning
	}
	event := LogEvent{
		Timestamp: start,
		Level:     level,
		Service:   gw.cfg.LoggingServiceName,
		Message:   "gateway request",
		TraceID:   metadata.RequestID,
		Metadata:  *metadata,
	}
	if err := gw.logger.Emit(ctx, event); err != nil {
		log.Printf("gateway log emit failed: %v", err)
	}
}

func (gw *gateway) newProxy() *httputil.ReverseProxy {
	proxy := httputil.NewSingleHostReverseProxy(gw.backend)
	if gw.transport != nil {
		proxy.Transport = gw.transport
	}
	originalDirector := proxy.Director
	proxy.Director = func(req *http.Request) {
		originalDirector(req)
		req.Host = gw.backend.Host
	}
	proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
		writeJSON(w, http.StatusBadGateway, map[string]string{"message": "upstream unavailable"})
	}
	return proxy
}

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

func isPublicPath(path string) bool {
	publicPaths := map[string]struct{}{
		"/ready":        {},
		"/docs":         {},
		"/redoc":        {},
		"/openapi.json": {},
	}
	if _, ok := publicPaths[path]; ok {
		return true
	}
	for _, prefix := range []string{
		"/api/v1/account/register-trial",
		"/api/v1/account/login",
		"/api/v1/account/send-verification-code",
		"/api/v1/account/leads",
	} {
		if strings.HasPrefix(path, prefix) {
			return true
		}
	}
	return false
}

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

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}
