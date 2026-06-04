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

var PaymentProtectedPathPrefixes = []string{
	"/api/v1/payment/native/prepay",
	"/api/v1/payment/orders/",
}

var PaymentPublicExactPaths = []string{
	"/webhooks/wechatpay/native",
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
	backendURL        string
	paymentServiceURL string
}

// NewDefaultRoutePolicy returns the current icore-agent route policy.
func NewDefaultRoutePolicy(backendURL string, paymentServiceURL ...string) RoutePolicy {
	paymentURL := ""
	if len(paymentServiceURL) > 0 {
		paymentURL = paymentServiceURL[0]
	}
	return RoutePolicy{backendURL: backendURL, paymentServiceURL: paymentURL}
}

// Resolve returns the route behavior for a request path.
func (policy RoutePolicy) Resolve(path string) Route {
	if path == "/health" {
		return Route{Public: true, LocalHealth: true}
	}
	if isPaymentPublicPath(path) {
		return Route{
			Public:          true,
			AuthRequired:    false,
			UpstreamService: "payment-service",
			UpstreamAddr:    policy.paymentServiceURL,
		}
	}
	if isPaymentProtectedPath(path) {
		return Route{
			Public:          false,
			AuthRequired:    true,
			UpstreamService: "payment-service",
			UpstreamAddr:    policy.paymentServiceURL,
		}
	}

	public := isPublicPath(path)
	return Route{
		Public:          public,
		AuthRequired:    !public,
		UpstreamService: "icore-agent",
		UpstreamAddr:    policy.backendURL,
	}
}

func isPaymentPublicPath(path string) bool {
	for _, exact := range PaymentPublicExactPaths {
		if path == exact {
			return true
		}
	}
	return false
}

func isPaymentProtectedPath(path string) bool {
	for _, prefix := range PaymentProtectedPathPrefixes {
		if strings.HasPrefix(path, prefix) {
			return true
		}
	}
	return false
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
