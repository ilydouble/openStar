package pipeline

import (
	"context"
	"errors"
	"icore-gateway/internal/application/identity_policy"
	"icore-gateway/internal/application/pipeline/deps"
	"icore-gateway/internal/application/route_policy"
	"icore-gateway/internal/domain/auth"
	domain2 "icore-gateway/internal/domain/identity"
	"icore-gateway/internal/domain/logging"
	"icore-gateway/internal/domain/rate_limit"
	"icore-gateway/internal/domain/request_id"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	sharedlogging "icore-services-lib-go/logging"
)

type fakeAuthenticator struct {
	identity domain2.Identity
	err      error
}

func (auth fakeAuthenticator) Authenticate(_ string, _ time.Time) (domain2.Identity, error) {
	return auth.identity, auth.err
}

type fakeLimiter struct {
	decision rate_limit.RateLimitDecision
}

func (limiter fakeLimiter) GetRateLimitDecision(_ context.Context, _ rate_limit.RateLimitTarget) (rate_limit.RateLimitDecision, error) {
	return limiter.decision, nil
}

type fakeProxy struct {
	hit       bool
	status    int
	userID    string
	userRoles string
	requestID string
}

func (proxy *fakeProxy) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	proxy.hit = true
	proxy.userID = r.Header.Get("X-User-ID")
	proxy.userRoles = r.Header.Get("X-User-Roles")
	proxy.requestID = r.Header.Get(request_id.RequestIDHeader)
	status := proxy.status
	if status == 0 {
		status = http.StatusOK
	}
	w.WriteHeader(status)
}

type captureAccessLogger struct {
	events []logging.AccessLogEvent
}

func (logger *captureAccessLogger) Emit(event logging.AccessLogEvent) {
	logger.events = append(logger.events, event)
}

type testResponseRecorder struct {
	*httptest.ResponseRecorder
}

func newTestResponseRecorder() *testResponseRecorder {
	return &testResponseRecorder{ResponseRecorder: httptest.NewRecorder()}
}

// Status returns the final recorded status, matching gateway response recorder behavior.
func (recorder *testResponseRecorder) Status() int {
	if recorder.Code == 0 {
		return http.StatusOK
	}
	return recorder.Code
}

// TestPipelineSkipsSuccessfulHealthProbeAccessLog verifies routine health probes stay quiet.
func TestPipelineSkipsSuccessfulHealthProbeAccessLog(t *testing.T) {
	logger := &captureAccessLogger{}
	pipeline := newTestPipeline(fakeAuthenticator{}, fakeLimiter{}, &fakeProxy{}, logger)

	response := newTestResponseRecorder()
	request := httptest.NewRequest(http.MethodGet, "/health", nil)
	pipeline.HandleHealth(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", response.Code)
	}
	if len(logger.events) != 0 {
		t.Fatalf("successful health probe logs = %d, want 0", len(logger.events))
	}
}

// TestPipelineLogsFailedHealthProbeAccessLog verifies failed health probes remain visible.
func TestPipelineLogsFailedHealthProbeAccessLog(t *testing.T) {
	logger := &captureAccessLogger{}
	pipeline := newTestPipeline(fakeAuthenticator{}, fakeLimiter{}, &fakeProxy{}, logger)
	response := newTestResponseRecorder()
	response.WriteHeader(http.StatusServiceUnavailable)
	metadata := &logging.AccessLogMetadata{
		RequestID:       "req-health-failed",
		Path:            "/health",
		Roles:           []string{},
		RateLimitResult: "skipped",
	}

	pipeline.emitLog(pipeline.now(), metadata, response)

	if len(logger.events) != 1 {
		t.Fatalf("failed health probe logs = %d, want 1", len(logger.events))
	}
	event := logger.events[0]
	if event.Level != sharedlogging.LogLevelError {
		t.Fatalf("level = %q, want error", event.Level)
	}
	if event.Metadata.FinalStatusCode != http.StatusServiceUnavailable {
		t.Fatalf("status = %d, want 503", event.Metadata.FinalStatusCode)
	}
}

func TestPipelineRejectsProtectedRouteWithoutTokenBeforeProxy(t *testing.T) {
	proxy := &fakeProxy{}
	logger := &captureAccessLogger{}
	pipeline := newTestPipeline(fakeAuthenticator{}, fakeLimiter{}, proxy, logger)

	response := newTestResponseRecorder()
	request := httptest.NewRequest(http.MethodGet, "/api/v1/account/me", nil)
	pipeline.HandleProxy(response, request)

	if response.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401", response.Code)
	}
	if proxy.hit {
		t.Fatal("protected request without token should not hit upstream")
	}
	if got := logger.events[0].Metadata.AuthResult; got != auth.AuthResultMissingToken {
		t.Fatalf("auth result = %q, want missing token", got)
	}
}

func TestPipelineClearsSpoofedIdentityHeadersOnPublicUpstream(t *testing.T) {
	proxy := &fakeProxy{}
	logger := &captureAccessLogger{}
	pipeline := newTestPipeline(fakeAuthenticator{}, fakeLimiter{
		decision: rate_limit.RateLimitDecision{Allowed: true, Result: "allowed"},
	}, proxy, logger)

	response := newTestResponseRecorder()
	request := httptest.NewRequest(http.MethodPost, "/api/v1/account/login", nil)
	request.Header.Set("X-User-ID", "attacker")
	request.Header.Set("X-User-Roles", "admin")
	pipeline.HandleProxy(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", response.Code)
	}
	if proxy.userID != "" || proxy.userRoles != "" {
		t.Fatalf("spoofed identity forwarded: user=%q roles=%q", proxy.userID, proxy.userRoles)
	}
	if proxy.requestID == "" {
		t.Fatal("upstream request should receive X-Request-ID")
	}
	if got := logger.events[0].Metadata.AuthResult; got != auth.AuthResultPublic {
		t.Fatalf("auth result = %q, want public", got)
	}
}

func TestPipelineForwardsAuthenticatedIdentity(t *testing.T) {
	proxy := &fakeProxy{}
	pipeline := newTestPipeline(fakeAuthenticator{
		identity: domain2.Identity{UserID: "user-1", Roles: []string{"owner", "admin"}},
	}, fakeLimiter{decision: rate_limit.RateLimitDecision{Allowed: true, Result: "allowed"}}, proxy, &captureAccessLogger{})

	response := newTestResponseRecorder()
	request := httptest.NewRequest(http.MethodGet, "/api/v1/account/me", nil)
	request.Header.Set("Authorization", "Bearer valid-token")
	pipeline.HandleProxy(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", response.Code)
	}
	if proxy.userID != "user-1" || proxy.userRoles != "owner,admin" {
		t.Fatalf("identity forwarded as user=%q roles=%q", proxy.userID, proxy.userRoles)
	}
}

func TestPipelineRecordsUpstreamErrorInAccessLog(t *testing.T) {
	proxy := &fakeProxy{status: http.StatusServiceUnavailable}
	logger := &captureAccessLogger{}
	pipeline := newTestPipeline(fakeAuthenticator{}, fakeLimiter{
		decision: rate_limit.RateLimitDecision{Allowed: true, Result: "allowed"},
	}, proxy, logger)

	response := newTestResponseRecorder()
	request := httptest.NewRequest(http.MethodPost, "/api/v1/account/login", nil)
	pipeline.HandleProxy(response, request)

	metadata := logger.events[0].Metadata
	if metadata.UpstreamStatusCode == nil || *metadata.UpstreamStatusCode != http.StatusServiceUnavailable {
		t.Fatalf("upstream status = %#v, want 503", metadata.UpstreamStatusCode)
	}
	if metadata.ErrorType == nil || *metadata.ErrorType != "upstream_error" {
		t.Fatalf("error type = %#v, want upstream_error", metadata.ErrorType)
	}
}

func TestPipelineRejectsInvalidToken(t *testing.T) {
	proxy := &fakeProxy{}
	logger := &captureAccessLogger{}
	pipeline := newTestPipeline(fakeAuthenticator{err: errors.New("bad token")}, fakeLimiter{}, proxy, logger)

	response := newTestResponseRecorder()
	request := httptest.NewRequest(http.MethodGet, "/api/v1/account/me", nil)
	request.Header.Set("Authorization", "Bearer invalid-token")
	pipeline.HandleProxy(response, request)

	if response.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401", response.Code)
	}
	if proxy.hit {
		t.Fatal("invalid token should not hit upstream")
	}
	if got := logger.events[0].Metadata.AuthResult; got != auth.AuthResultInvalidToken {
		t.Fatalf("auth result = %q, want invalid token", got)
	}
}

func newTestPipeline(auth deps.Authenticator, limiter deps.RateLimiter, proxy deps.UpstreamProxy, logger deps.AccessLogger) *Pipeline {
	return NewPipeline(PipelineConfig{
		ServiceName: "icore-gateway",
		RoutePolicy: route_policy.NewDefaultRoutePolicy("http://backend.local"),
		RequestIDPolicy: request_id.RequestIDPolicy{
			Generate: func() string { return "generated-request-id" },
		},
		IdentityPolicy: identity_policy.IdentityPolicy{},
		Location:       time.FixedZone("CST", 8*3600),
		Now: func() time.Time {
			return time.Date(2026, 5, 16, 15, 22, 0, 0, time.FixedZone("CST", 8*3600))
		},
	}, deps.PipelineDependencies{
		Authenticator:  auth,
		ServiceLimiter: limiter,
		Proxy:          proxy,
		AccessLogger:   logger,
	})
}
