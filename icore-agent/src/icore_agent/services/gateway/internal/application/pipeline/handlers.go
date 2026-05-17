package pipeline

import (
	pipeline_deps "icore-gateway/internal/application/pipeline/deps"
	"icore-gateway/internal/domain/auth"
	"icore-gateway/internal/domain/rate_limit"
	"net/http"
)

// HandleHealth handles the gateway-local health endpoint.
func (pipeline *Pipeline) HandleHealth(recorder ResponseStatusRecorder, r *http.Request) {
	route := pipeline.routePolicy.Resolve(r.URL.Path)
	metadata, start := pipeline.beginRequest(recorder, r, route)
	metadata.AuthResult = auth.AuthResultPublic
	metadata.RateLimitResult = "skipped"
	writeJSON(recorder, http.StatusOK, map[string]string{"status": "ok", "service": pipeline.serviceName})
	pipeline.emitLog(start, metadata, recorder)
}

// HandleProxy handles upstream gateway requests.
func (pipeline *Pipeline) HandleProxy(recorder ResponseStatusRecorder, r *http.Request) {
	route := pipeline.routePolicy.Resolve(r.URL.Path)
	metadata, start := pipeline.beginRequest(recorder, r, route)
	defer pipeline.emitLog(start, metadata, recorder)
	rateResults := pipeline_deps.NewRateLimitResults()

	if !pipeline.isAllowedByLimiter(r.Context(), metadata, rateResults, pipeline.deps.ClientIPLimiter, rate_limit.RateLimitTarget{
		Scope: rate_limit.RateLimitScopeClientIP,
		Key:   metadata.ClientIP,
	}) {
		writeJSON(recorder, http.StatusTooManyRequests, map[string]string{"message": "rate limit exceeded"})
		return
	}
	identity, ok := pipeline.authenticate(r, metadata, route)
	if !ok {
		rateResults.SetSkipped(rate_limit.RateLimitScopeUserID)
		rateResults.SetSkipped(rate_limit.RateLimitScopeService)
		metadata.RateLimitResult = rateResults.String()
		writeJSON(recorder, http.StatusUnauthorized, map[string]string{"message": "unauthorized"})
		return
	}
	if identity != nil {
		if !pipeline.isAllowedByLimiter(r.Context(), metadata, rateResults, pipeline.deps.UserIDLimiter, rate_limit.RateLimitTarget{
			Scope: rate_limit.RateLimitScopeUserID,
			Key:   identity.UserID,
		}) {
			writeJSON(recorder, http.StatusTooManyRequests, map[string]string{"message": "rate limit exceeded"})
			return
		}
	} else {
		rateResults.SetSkipped(rate_limit.RateLimitScopeUserID)
		metadata.RateLimitResult = rateResults.String()
	}
	if !pipeline.isAllowedByLimiter(r.Context(), metadata, rateResults, pipeline.deps.ServiceLimiter, rate_limit.RateLimitTarget{
		Scope: rate_limit.RateLimitScopeService,
		Key:   route.UpstreamService,
	}) {
		writeJSON(recorder, http.StatusTooManyRequests, map[string]string{"message": "rate limit exceeded"})
		return
	}
	pipeline.identityPolicy.Apply(r.Header, identity)

	if pipeline.deps.Proxy != nil {
		pipeline.deps.Proxy.ServeHTTP(recorder, r)
	}
	if route.UpstreamService != "" {
		status := recorder.Status()
		metadata.UpstreamStatusCode = &status
	}
}
