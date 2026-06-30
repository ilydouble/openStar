package identity_policy

import (
	"icore-gateway/internal/domain/identity"
	"net/http"
	"strings"

	sharedheaders "icore-services-lib-go/http/headers"
)

const (
	userIDHeader    = sharedheaders.HeaderXUserID
	userRolesHeader = sharedheaders.HeaderXUserRoles
)

// IdentityPolicy sanitizes caller-supplied identity headers and forwards trusted identity.
type IdentityPolicy struct{}

// Apply clears spoofable identity headers and injects authenticated identity when present.
func (policy IdentityPolicy) Apply(header http.Header, identity *identity.Identity) {
	header.Del(userIDHeader)
	header.Del(userRolesHeader)
	if identity == nil {
		return
	}
	if strings.TrimSpace(identity.UserID) != "" {
		header.Set(userIDHeader, identity.UserID)
	}
	if len(identity.Roles) > 0 {
		header.Set(userRolesHeader, strings.Join(identity.Roles, ","))
	}
}
