package pipeline

import (
	pipeline_deps "icore-gateway/internal/application/pipeline/deps"
	"icore-gateway/internal/application/route_policy"
	"icore-gateway/internal/domain/auth"
	identitydomain "icore-gateway/internal/domain/identity"
	"icore-gateway/internal/domain/logging"
	"icore-gateway/internal/domain/rate_limit"
	"net/http"
	"time"
)

// GatewayContext carries shared request state across gateway pipeline stages.
type GatewayContext struct {
	Recorder    ResponseStatusRecorder
	Request     *http.Request
	Route       route_policy.Route
	Metadata    *logging.AccessLogMetadata
	Identity    *identitydomain.Identity
	RateResults *pipeline_deps.RateLimitResults
	StartedAt   time.Time
}

// GatewayStage performs one gateway pipeline step and returns false to stop the chain.
type GatewayStage func(*GatewayContext) bool

// runGatewayStages creates request context, runs stages, and emits one access log.
func (pipeline *Pipeline) runGatewayStages(recorder ResponseStatusRecorder, r *http.Request, stages ...GatewayStage) {
	gatewayContext := pipeline.newGatewayContext(recorder, r)
	defer pipeline.emitLog(gatewayContext.StartedAt, gatewayContext.Metadata, recorder)
	runStageChain(gatewayContext, stages...)
}

// newGatewayContext resolves route metadata and initializes per-request stage state.
func (pipeline *Pipeline) newGatewayContext(recorder ResponseStatusRecorder, r *http.Request) *GatewayContext {
	route := pipeline.routePolicy.Resolve(r.URL.Path)
	metadata, start := pipeline.beginRequest(recorder, r, route)
	return &GatewayContext{
		Recorder:    recorder,
		Request:     r,
		Route:       route,
		Metadata:    metadata,
		RateResults: pipeline_deps.NewRateLimitResults(),
		StartedAt:   start,
	}
}

// runStageChain executes stages in order until one stage stops the chain.
func runStageChain(gatewayContext *GatewayContext, stages ...GatewayStage) bool {
	for _, stage := range stages {
		if !stage(gatewayContext) {
			return false
		}
	}
	return true
}

// healthResponseStage writes the gateway-local health response.
func (pipeline *Pipeline) healthResponseStage(gatewayContext *GatewayContext) bool {
	gatewayContext.Metadata.AuthResult = auth.AuthResultPublic
	gatewayContext.Metadata.RateLimitResult = "skipped"
	writeJSON(
		gatewayContext.Recorder,
		http.StatusOK,
		map[string]string{"status": "ok", "service": pipeline.serviceName},
	)
	return true
}

// clientIPRateLimitStage applies the client IP limiter before auth and upstream work.
func (pipeline *Pipeline) clientIPRateLimitStage(gatewayContext *GatewayContext) bool {
	if pipeline.isAllowedByLimiter(
		gatewayContext.Request.Context(),
		gatewayContext.Metadata,
		gatewayContext.RateResults,
		pipeline.deps.ClientIPLimiter,
		rate_limit.RateLimitTarget{
			Scope: rate_limit.RateLimitScopeClientIP,
			Key:   gatewayContext.Metadata.ClientIP,
		},
	) {
		return true
	}
	writeJSON(gatewayContext.Recorder, http.StatusTooManyRequests, map[string]string{"message": "rate limit exceeded"})
	return false
}

// authenticationStage authenticates protected routes and records the request identity.
func (pipeline *Pipeline) authenticationStage(gatewayContext *GatewayContext) bool {
	identity, ok := pipeline.authenticate(gatewayContext.Request, gatewayContext.Metadata, gatewayContext.Route)
	if ok {
		gatewayContext.Identity = identity
		return true
	}
	gatewayContext.RateResults.SetSkipped(rate_limit.RateLimitScopeUserID)
	gatewayContext.RateResults.SetSkipped(rate_limit.RateLimitScopeService)
	gatewayContext.Metadata.RateLimitResult = gatewayContext.RateResults.String()
	writeJSON(gatewayContext.Recorder, http.StatusUnauthorized, map[string]string{"message": "unauthorized"})
	return false
}

// userIDRateLimitStage applies user limits only after a protected route is authenticated.
func (pipeline *Pipeline) userIDRateLimitStage(gatewayContext *GatewayContext) bool {
	if gatewayContext.Identity == nil {
		gatewayContext.RateResults.SetSkipped(rate_limit.RateLimitScopeUserID)
		gatewayContext.Metadata.RateLimitResult = gatewayContext.RateResults.String()
		return true
	}
	if pipeline.isAllowedByLimiter(
		gatewayContext.Request.Context(),
		gatewayContext.Metadata,
		gatewayContext.RateResults,
		pipeline.deps.UserIDLimiter,
		rate_limit.RateLimitTarget{
			Scope: rate_limit.RateLimitScopeUserID,
			Key:   gatewayContext.Identity.UserID,
		},
	) {
		return true
	}
	writeJSON(gatewayContext.Recorder, http.StatusTooManyRequests, map[string]string{"message": "rate limit exceeded"})
	return false
}

// serviceRateLimitStage applies the upstream service limiter before proxying.
func (pipeline *Pipeline) serviceRateLimitStage(gatewayContext *GatewayContext) bool {
	if pipeline.isAllowedByLimiter(
		gatewayContext.Request.Context(),
		gatewayContext.Metadata,
		gatewayContext.RateResults,
		pipeline.deps.ServiceLimiter,
		rate_limit.RateLimitTarget{
			Scope: rate_limit.RateLimitScopeService,
			Key:   gatewayContext.Route.UpstreamService,
		},
	) {
		return true
	}
	writeJSON(gatewayContext.Recorder, http.StatusTooManyRequests, map[string]string{"message": "rate limit exceeded"})
	return false
}

// identityHeaderStage strips spoofed headers and forwards trusted identity headers.
func (pipeline *Pipeline) identityHeaderStage(gatewayContext *GatewayContext) bool {
	pipeline.identityPolicy.Apply(gatewayContext.Request.Header, gatewayContext.Identity)
	return true
}

// proxyStage forwards the request to the selected upstream and records its status.
func (pipeline *Pipeline) proxyStage(gatewayContext *GatewayContext) bool {
	if pipeline.deps.Proxy != nil {
		pipeline.deps.Proxy.ServeHTTP(gatewayContext.Recorder, gatewayContext.Request)
	}
	if gatewayContext.Route.UpstreamService != "" {
		status := gatewayContext.Recorder.Status()
		gatewayContext.Metadata.UpstreamStatusCode = &status
	}
	return true
}
