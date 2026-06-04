package route_policy

import "testing"

func TestDefaultRoutePolicyClassifiesLocalHealth(t *testing.T) {
	policy := NewDefaultRoutePolicy("http://backend.local")

	route := policy.Resolve("/health")

	if !route.Public || route.AuthRequired || !route.LocalHealth {
		t.Fatalf("health route = %#v, want public local health", route)
	}
	if route.UpstreamService != "" || route.UpstreamAddr != "" {
		t.Fatalf("health route should not have upstream: %#v", route)
	}
}

func TestDefaultRoutePolicyClassifiesPublicUpstreamPrefixes(t *testing.T) {
	policy := NewDefaultRoutePolicy("http://backend.local", "http://payment.local")

	route := policy.Resolve("/api/v1/account/send-verification-code")

	if !route.Public || route.AuthRequired || route.LocalHealth {
		t.Fatalf("public upstream route = %#v", route)
	}
	if route.UpstreamService != "icore-agent" || route.UpstreamAddr != "http://backend.local" {
		t.Fatalf("public upstream target = %#v", route)
	}
}

func TestDefaultRoutePolicyProtectsUnknownAPIPaths(t *testing.T) {
	policy := NewDefaultRoutePolicy("http://backend.local", "http://payment.local")

	route := policy.Resolve("/api/v1/account/me")

	if route.Public || !route.AuthRequired || route.LocalHealth {
		t.Fatalf("protected route = %#v", route)
	}
}

func TestDefaultRoutePolicyProtectsPaymentAPIAndTargetsPaymentService(t *testing.T) {
	policy := NewDefaultRoutePolicy("http://backend.local", "http://payment.local")

	route := policy.Resolve("/api/v1/payment/native/prepay")

	if route.Public || !route.AuthRequired || route.LocalHealth {
		t.Fatalf("payment route = %#v, want protected upstream", route)
	}
	if route.UpstreamService != "payment-service" || route.UpstreamAddr != "http://payment.local" {
		t.Fatalf("payment upstream target = %#v", route)
	}
}

func TestDefaultRoutePolicyRoutesWechatPayWebhookPubliclyToPaymentService(t *testing.T) {
	policy := NewDefaultRoutePolicy("http://backend.local", "http://payment.local")

	route := policy.Resolve("/webhooks/wechatpay/native")

	if !route.Public || route.AuthRequired || route.LocalHealth {
		t.Fatalf("wechatpay webhook route = %#v, want public upstream", route)
	}
	if route.UpstreamService != "payment-service" || route.UpstreamAddr != "http://payment.local" {
		t.Fatalf("wechatpay webhook upstream target = %#v", route)
	}
}
