package route_policy

import "strings"

var PublicExactPaths = []string{
	"/health",
	"/ready",
	"/docs",
	"/redoc",
	"/openapi.json",
}

var PublicPathPrefixes = []string{
	"/api/v1/account/register-trial",
	"/api/v1/account/login",
	"/api/v1/account/send-verification-code",
	"/api/v1/account/leads",
}

// Route describes how the gateway should handle one request path.
type Route struct {
	Public          bool
	AuthRequired    bool
	LocalHealth     bool
	UpstreamService string
	UpstreamAddr    string
}

// RoutePolicy classifies request paths into local and upstream gateway behavior.
type RoutePolicy struct {
	backendURL string
}

// NewDefaultRoutePolicy returns the current icore-agent route policy.
func NewDefaultRoutePolicy(backendURL string) RoutePolicy {
	return RoutePolicy{backendURL: backendURL}
}

// Resolve returns the route behavior for a request path.
func (policy RoutePolicy) Resolve(path string) Route {
	if path == "/health" {
		return Route{Public: true, LocalHealth: true}
	}

	public := isPublicPath(path)
	return Route{
		Public:          public,
		AuthRequired:    !public,
		UpstreamService: "icore-agent",
		UpstreamAddr:    policy.backendURL,
	}
}

func isPublicPath(path string) bool {
	for _, exact := range PublicExactPaths {
		if path == exact {
			return true
		}
	}
	for _, prefix := range PublicPathPrefixes {
		if strings.HasPrefix(path, prefix) {
			return true
		}
	}
	return false
}
