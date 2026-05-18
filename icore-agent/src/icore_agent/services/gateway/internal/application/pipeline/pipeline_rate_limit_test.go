package pipeline

import (
	"context"
	"icore-gateway/internal/application/identity_policy"
	"icore-gateway/internal/application/pipeline/deps"
	"icore-gateway/internal/application/route_policy"
	domain2 "icore-gateway/internal/domain/identity"
	"icore-gateway/internal/domain/rate_limit"
	"icore-gateway/internal/domain/request_id"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

type limiterCall struct {
	name   string
	target rate_limit.RateLimitTarget
}

type recordingLimiter struct {
	name     string
	decision rate_limit.RateLimitDecision
	calls    *[]limiterCall
	order    *[]string
}

func (limiter recordingLimiter) GetRateLimitDecision(_ context.Context, target rate_limit.RateLimitTarget) (rate_limit.RateLimitDecision, error) {
	*limiter.calls = append(*limiter.calls, limiterCall{name: limiter.name, target: target})
	if limiter.order != nil {
		*limiter.order = append(*limiter.order, limiter.name)
	}
	return limiter.decision, nil
}

type orderedAuthenticator struct {
	identity domain2.Identity
	order    *[]string
}

func (auth orderedAuthenticator) Authenticate(_ string, _ time.Time) (domain2.Identity, error) {
	*auth.order = append(*auth.order, "auth")
	return auth.identity, nil
}

type orderedProxy struct {
	hit   bool
	order *[]string
}

func (proxy *orderedProxy) ServeHTTP(w http.ResponseWriter, _ *http.Request) {
	proxy.hit = true
	*proxy.order = append(*proxy.order, "proxy")
	w.WriteHeader(http.StatusOK)
}

func TestPipelineRejectsClientIPBeforeAuthProxyAndOtherLimiters(t *testing.T) {
	limiterCalls := []limiterCall{}
	order := []string{}
	proxy := &orderedProxy{order: &order}
	logger := &captureAccessLogger{}
	pipeline := newRateLimitTestPipeline(
		orderedAuthenticator{identity: domain2.Identity{UserID: "user-1"}, order: &order},
		recordingLimiter{name: "client_ip", calls: &limiterCalls, decision: rate_limit.RateLimitDecision{Allowed: false, Result: "rejected"}},
		recordingLimiter{name: "user_id", calls: &limiterCalls, decision: rate_limit.RateLimitDecision{Allowed: true, Result: "allowed"}},
		recordingLimiter{name: "service", calls: &limiterCalls, decision: rate_limit.RateLimitDecision{Allowed: true, Result: "allowed"}},
		proxy,
		logger,
	)

	response := newTestResponseRecorder()
	request := httptest.NewRequest(http.MethodGet, "/api/v1/account/me", nil)
	request.RemoteAddr = "203.0.113.10:54321"
	request.Header.Set("Authorization", "Bearer valid-token")
	pipeline.HandleProxy(response, request)

	if response.Code != http.StatusTooManyRequests {
		t.Fatalf("status = %d, want 429", response.Code)
	}
	if proxy.hit {
		t.Fatal("client_ip rejected request should not hit upstream")
	}
	if len(order) != 0 {
		t.Fatalf("order = %#v, want no auth/proxy calls", order)
	}
	if len(limiterCalls) != 1 {
		t.Fatalf("limiter calls = %#v, want only client_ip", limiterCalls)
	}
	if limiterCalls[0].target.Scope != rate_limit.RateLimitScopeClientIP || limiterCalls[0].target.Key != "203.0.113.10" {
		t.Fatalf("client_ip target = %#v", limiterCalls[0].target)
	}
	metadata := logger.events[0].Metadata
	if metadata.RateLimitResult != "client_ip:rejected" {
		t.Fatalf("rate limit result = %q", metadata.RateLimitResult)
	}
	if metadata.RejectReason == nil || *metadata.RejectReason != "client_ip rate limit exceeded" {
		t.Fatalf("reject reason = %#v", metadata.RejectReason)
	}
}

func TestPipelineRunsLimitersInClientAuthUserServiceProxyOrder(t *testing.T) {
	limiterCalls := []limiterCall{}
	order := []string{}
	proxy := &orderedProxy{order: &order}
	logger := &captureAccessLogger{}
	pipeline := newRateLimitTestPipeline(
		orderedAuthenticator{identity: domain2.Identity{UserID: "user-1", Roles: []string{"admin"}}, order: &order},
		orderedLimiter("client_ip", &limiterCalls, &order),
		orderedLimiter("user_id", &limiterCalls, &order),
		orderedLimiter("service", &limiterCalls, &order),
		proxy,
		logger,
	)

	response := newTestResponseRecorder()
	request := httptest.NewRequest(http.MethodGet, "/api/v1/account/me", nil)
	request.RemoteAddr = "198.51.100.9:12345"
	request.Header.Set("Authorization", "Bearer valid-token")
	pipeline.HandleProxy(response, request)

	wantOrder := []string{"client_ip", "auth", "user_id", "service", "proxy"}
	if !equalStrings(order, wantOrder) {
		t.Fatalf("order = %#v, want %#v", order, wantOrder)
	}
	if got := limiterCalls[0].target; got.Scope != rate_limit.RateLimitScopeClientIP || got.Key != "198.51.100.9" {
		t.Fatalf("client_ip target = %#v", got)
	}
	if got := limiterCalls[1].target; got.Scope != rate_limit.RateLimitScopeUserID || got.Key != "user-1" {
		t.Fatalf("user_id target = %#v", got)
	}
	if got := limiterCalls[2].target; got.Scope != rate_limit.RateLimitScopeService || got.Key != "icore-agent" {
		t.Fatalf("service target = %#v", got)
	}
	if got := logger.events[0].Metadata.RateLimitResult; got != "client_ip:allowed,user_id:allowed,service:allowed" {
		t.Fatalf("rate limit result = %q", got)
	}
}

func TestPipelinePublicRouteSkipsUserIDLimiter(t *testing.T) {
	limiterCalls := []limiterCall{}
	order := []string{}
	proxy := &orderedProxy{order: &order}
	logger := &captureAccessLogger{}
	pipeline := newRateLimitTestPipeline(
		orderedAuthenticator{identity: domain2.Identity{UserID: "user-1"}, order: &order},
		orderedLimiter("client_ip", &limiterCalls, &order),
		orderedLimiter("user_id", &limiterCalls, &order),
		orderedLimiter("service", &limiterCalls, &order),
		proxy,
		logger,
	)

	response := newTestResponseRecorder()
	request := httptest.NewRequest(http.MethodPost, "/api/v1/account/login", nil)
	request.RemoteAddr = "192.0.2.8:4444"
	pipeline.HandleProxy(response, request)

	wantOrder := []string{"client_ip", "service", "proxy"}
	if !equalStrings(order, wantOrder) {
		t.Fatalf("order = %#v, want %#v", order, wantOrder)
	}
	if got := logger.events[0].Metadata.RateLimitResult; got != "client_ip:allowed,user_id:skipped,service:allowed" {
		t.Fatalf("rate limit result = %q", got)
	}
}

func TestPipelineRejectsServiceLimitBeforeProxy(t *testing.T) {
	limiterCalls := []limiterCall{}
	order := []string{}
	proxy := &orderedProxy{order: &order}
	logger := &captureAccessLogger{}
	pipeline := newRateLimitTestPipeline(
		orderedAuthenticator{identity: domain2.Identity{UserID: "user-1"}, order: &order},
		orderedLimiter("client_ip", &limiterCalls, &order),
		orderedLimiter("user_id", &limiterCalls, &order),
		recordingLimiter{name: "service", calls: &limiterCalls, decision: rate_limit.RateLimitDecision{Allowed: false, Result: "rejected"}},
		proxy,
		logger,
	)

	response := newTestResponseRecorder()
	request := httptest.NewRequest(http.MethodGet, "/api/v1/account/me", nil)
	request.Header.Set("Authorization", "Bearer valid-token")
	pipeline.HandleProxy(response, request)

	if response.Code != http.StatusTooManyRequests {
		t.Fatalf("status = %d, want 429", response.Code)
	}
	if proxy.hit {
		t.Fatal("service rejected request should not hit upstream")
	}
	metadata := logger.events[0].Metadata
	if metadata.RateLimitResult != "client_ip:allowed,user_id:allowed,service:rejected" {
		t.Fatalf("rate limit result = %q", metadata.RateLimitResult)
	}
	if metadata.RejectReason == nil || *metadata.RejectReason != "service rate limit exceeded" {
		t.Fatalf("reject reason = %#v", metadata.RejectReason)
	}
}

func orderedLimiter(name string, calls *[]limiterCall, order *[]string) recordingLimiter {
	return recordingLimiter{
		name:  name,
		calls: calls,
		order: order,
		decision: rate_limit.RateLimitDecision{
			Allowed: true,
			Result:  "allowed",
		},
	}
}

func newRateLimitTestPipeline(
	auth deps.Authenticator,
	clientIPLimiter deps.ClientIPLimiter,
	userIDLimiter deps.UserIDLimiter,
	serviceLimiter deps.ServiceLimiter,
	proxy deps.UpstreamProxy,
	logger deps.AccessLogger,
) *Pipeline {
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
		Authenticator:   auth,
		ClientIPLimiter: clientIPLimiter,
		UserIDLimiter:   userIDLimiter,
		ServiceLimiter:  serviceLimiter,
		AccessLogger:    logger,
		Proxy:           proxy,
	})
}

func equalStrings(left []string, right []string) bool {
	if len(left) != len(right) {
		return false
	}
	for index := range left {
		if left[index] != right[index] {
			return false
		}
	}
	return true
}
