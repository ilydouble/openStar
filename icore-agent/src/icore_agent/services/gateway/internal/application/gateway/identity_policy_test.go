package gateway

import (
	"net/http"
	"testing"

	domain "icore-gateway/internal/domain/gateway"
)

func TestIdentityPolicyClearsSpoofedIdentityHeadersForPublicRequests(t *testing.T) {
	header := http.Header{}
	header.Set("X-User-ID", "attacker")
	header.Set("X-User-Roles", "admin")

	IdentityPolicy{}.Apply(header, nil)

	if got := header.Get("X-User-ID"); got != "" {
		t.Fatalf("X-User-ID = %q, want cleared", got)
	}
	if got := header.Get("X-User-Roles"); got != "" {
		t.Fatalf("X-User-Roles = %q, want cleared", got)
	}
}

func TestIdentityPolicyForwardsAuthenticatedIdentity(t *testing.T) {
	header := http.Header{}
	identity := &domain.Identity{UserID: "user-1", Roles: []string{"owner", "admin"}}

	IdentityPolicy{}.Apply(header, identity)

	if got := header.Get("X-User-ID"); got != "user-1" {
		t.Fatalf("X-User-ID = %q, want user-1", got)
	}
	if got := header.Get("X-User-Roles"); got != "owner,admin" {
		t.Fatalf("X-User-Roles = %q, want owner,admin", got)
	}
}
