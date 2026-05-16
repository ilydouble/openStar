package gateway

import (
	"context"
	"encoding/json"
	"net"
	"net/http"
	"strings"
	"time"

	domain "icore-gateway/internal/domain/gateway"
	sharedlogging "icore-services-lib-go/logging"
)

// Authenticator validates bearer tokens and returns an upstream identity.
type Authenticator interface {
	Authenticate(token string, now time.Time) (domain.Identity, error)
}

// RateLimiter decides whether a request may enter an upstream service.
type RateLimiter interface {
	Allow(context.Context, string) (domain.RateLimitDecision, error)
}

// UpstreamProxy forwards a request to the selected upstream service.
type UpstreamProxy interface {
	ServeHTTP(http.ResponseWriter, *http.Request)
}

// AccessLogger accepts completed gateway access log events.
type AccessLogger interface {
	Emit(domain.AccessLogEvent)
}

// ResponseRecorder is the HTTP response surface the pipeline needs to finalize logs.
type ResponseRecorder interface {
	http.ResponseWriter
	Status() int
}

// PipelineConfig configures gateway request orchestration.
type PipelineConfig struct {
	ServiceName     string
	RoutePolicy     RoutePolicy
	RequestIDPolicy domain.RequestIDPolicy
	IdentityPolicy  IdentityPolicy
	Location        *time.Location
	Now             func() time.Time
}

// PipelineDependencies are side-effecting collaborators used by Pipeline.
type PipelineDependencies struct {
	Authenticator Authenticator
	Limiter       RateLimiter
	Proxy         UpstreamProxy
	AccessLogger  AccessLogger
}

// Pipeline orchestrates request-id, route policy, auth, rate limit, proxy, and access log.
type Pipeline struct {
	serviceName     string
	routePolicy     RoutePolicy
	requestIDPolicy domain.RequestIDPolicy
	identityPolicy  IdentityPolicy
	location        *time.Location
	now             func() time.Time
	authenticator   Authenticator
	limiter         RateLimiter
	proxy           UpstreamProxy
	accessLogger    AccessLogger
}

// NewPipeline creates the application gateway pipeline.
func NewPipeline(config PipelineConfig, deps PipelineDependencies) *Pipeline {
	serviceName := config.ServiceName
	if serviceName == "" {
		serviceName = "icore-gateway"
	}
	location := config.Location
	if location == nil {
		location = time.Local
	}
	now := config.Now
	if now == nil {
		now = time.Now
	}
	return &Pipeline{
		serviceName:     serviceName,
		routePolicy:     config.RoutePolicy,
		requestIDPolicy: config.RequestIDPolicy,
		identityPolicy:  config.IdentityPolicy,
		location:        location,
		now:             now,
		authenticator:   deps.Authenticator,
		limiter:         deps.Limiter,
		proxy:           deps.Proxy,
		accessLogger:    deps.AccessLogger,
	}
}

// HandleHealth handles the gateway-local health endpoint.
func (pipeline *Pipeline) HandleHealth(recorder ResponseRecorder, r *http.Request) {
	route := pipeline.routePolicy.Resolve(r.URL.Path)
	metadata, start := pipeline.beginRequest(recorder, r, route)
	defer pipeline.emitLog(start, metadata, recorder)

	metadata.AuthResult = domain.AuthResultPublic
	metadata.RateLimitResult = "skipped"
	writeJSON(recorder, http.StatusOK, map[string]string{"status": "ok", "service": pipeline.serviceName})
}

// HandleProxy handles upstream gateway requests.
func (pipeline *Pipeline) HandleProxy(recorder ResponseRecorder, r *http.Request) {
	route := pipeline.routePolicy.Resolve(r.URL.Path)
	metadata, start := pipeline.beginRequest(recorder, r, route)
	defer pipeline.emitLog(start, metadata, recorder)

	identity, ok := pipeline.authenticate(r, metadata, route)
	if !ok {
		writeJSON(recorder, http.StatusUnauthorized, map[string]string{"message": "unauthorized"})
		return
	}
	pipeline.identityPolicy.Apply(r.Header, identity)

	if !pipeline.allowRequest(r.Context(), metadata, route) {
		writeJSON(recorder, http.StatusTooManyRequests, map[string]string{"message": "rate limit exceeded"})
		return
	}

	if pipeline.proxy != nil {
		pipeline.proxy.ServeHTTP(recorder, r)
	}
	if route.UpstreamService != "" {
		status := recorder.Status()
		metadata.UpstreamStatusCode = &status
	}
}

func (pipeline *Pipeline) beginRequest(w http.ResponseWriter, r *http.Request, route Route) (*domain.AccessLogMetadata, time.Time) {
	start := pipeline.now().In(pipeline.location)
	requestID := pipeline.requestIDPolicy.Resolve(r.Header.Get(domain.RequestIDHeader))
	r.Header.Set(domain.RequestIDHeader, requestID)
	w.Header().Set(domain.RequestIDHeader, requestID)

	metadata := &domain.AccessLogMetadata{
		RequestTimestamp: start.Format(time.RFC3339Nano),
		RequestID:        requestID,
		Method:           r.Method,
		Path:             r.URL.Path,
		Query:            r.URL.RawQuery,
		ClientIP:         clientIP(r),
		AuthResult:       "skipped",
		UserAgent:        classifyUserAgent(r.UserAgent()),
		Roles:            []string{},
		RateLimitResult:  "skipped",
	}
	if route.UpstreamService != "" {
		service := route.UpstreamService
		addr := route.UpstreamAddr
		metadata.UpstreamService = &service
		metadata.UpstreamAddr = &addr
	}
	return metadata, start
}

func (pipeline *Pipeline) authenticate(r *http.Request, metadata *domain.AccessLogMetadata, route Route) (*domain.Identity, bool) {
	if !route.AuthRequired {
		metadata.AuthResult = domain.AuthResultPublic
		return nil, true
	}
	raw := strings.TrimSpace(r.Header.Get("Authorization"))
	if !strings.HasPrefix(raw, "Bearer ") {
		metadata.AuthResult = domain.AuthResultMissingToken
		reason := "missing bearer token"
		metadata.RejectReason = &reason
		return nil, false
	}
	if pipeline.authenticator == nil {
		metadata.AuthResult = domain.AuthResultInvalidToken
		reason := "missing authenticator"
		metadata.RejectReason = &reason
		errorType := "auth_error"
		metadata.ErrorType = &errorType
		return nil, false
	}
	identity, err := pipeline.authenticator.Authenticate(strings.TrimSpace(strings.TrimPrefix(raw, "Bearer ")), pipeline.now())
	if err != nil {
		metadata.AuthResult = domain.AuthResultInvalidToken
		reason := "invalid bearer token"
		metadata.RejectReason = &reason
		errorType := "auth_error"
		metadata.ErrorType = &errorType
		return nil, false
	}
	metadata.AuthResult = domain.AuthResultSuccess
	metadata.UserID = identity.UserID
	metadata.Roles = identity.Roles
	return &identity, true
}

func (pipeline *Pipeline) allowRequest(ctx context.Context, metadata *domain.AccessLogMetadata, route Route) bool {
	if route.UpstreamService == "" || pipeline.limiter == nil {
		metadata.RateLimitResult = "skipped"
		return true
	}
	decision, err := pipeline.limiter.Allow(ctx, route.UpstreamService)
	if err != nil {
		metadata.RateLimitResult = "error"
		errorType := "rate_limit_error"
		metadata.ErrorType = &errorType
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

func (pipeline *Pipeline) emitLog(start time.Time, metadata *domain.AccessLogMetadata, recorder ResponseRecorder) {
	metadata.FinalStatusCode = recorder.Status()
	metadata.RequestElapsedTime = pipeline.now().Sub(start).Milliseconds()
	if metadata.FinalStatusCode >= http.StatusInternalServerError {
		errorType := "upstream_error"
		metadata.ErrorType = &errorType
	}
	if pipeline.accessLogger == nil {
		return
	}
	level := sharedlogging.LogLevelInfo
	if metadata.FinalStatusCode >= http.StatusInternalServerError {
		level = sharedlogging.LogLevelError
	} else if metadata.FinalStatusCode >= http.StatusBadRequest {
		level = sharedlogging.LogLevelWarning
	}
	pipeline.accessLogger.Emit(domain.AccessLogEvent{
		Timestamp: start,
		Level:     level,
		Service:   pipeline.serviceName,
		Message:   "gateway request",
		TraceID:   metadata.RequestID,
		Metadata:  *metadata,
	})
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
