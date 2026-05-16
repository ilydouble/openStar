package handler

import (
	"net/http"
	"net/http/httputil"
	"net/url"
	"time"

	"icore-gateway/internal/gateway"
	sharedlogging "icore-services-lib-go/logging"
)

const requestIDHeader = "X-Request-ID"

type identity struct {
	userID string
	roles  []string
}

// Handler owns gateway HTTP handlers and their side-effecting dependencies.
type Handler struct {
	cfg       gateway.Config
	logger    sharedlogging.Emitter
	limiter   gateway.RateLimiter
	transport http.RoundTripper
	now       func() time.Time
	location  *time.Location
	backend   *url.URL
	proxy     *httputil.ReverseProxy
}

// New creates gateway handlers for health checks and upstream proxying.
func New(cfg gateway.Config, deps gateway.Dependencies) *Handler {
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

	handler := &Handler{
		cfg:       cfg,
		logger:    deps.Logger,
		limiter:   deps.Limiter,
		transport: deps.Transport,
		now:       now,
		location:  location,
		backend:   backend,
	}
	handler.proxy = handler.newProxy()
	return handler
}
