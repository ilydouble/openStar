package handler

import (
	"net/http"
	"strings"

	"icore-gateway/internal/gateway"
)

// authenticate validates public routes or bearer JWTs and records the auth result.
func (handler *Handler) authenticate(r *http.Request, metadata *gateway.GatewayMetadata) (*identity, bool) {
	if isPublicPath(r.URL.Path) {
		metadata.AuthResult = gateway.AuthResultPublic
		return nil, true
	}

	raw := strings.TrimSpace(r.Header.Get("Authorization"))
	if !strings.HasPrefix(raw, "Bearer ") {
		metadata.AuthResult = gateway.AuthResultMissingToken
		reason := "missing bearer token"
		metadata.RejectReason = &reason
		return nil, false
	}

	claims, err := gateway.ValidateJWT(strings.TrimSpace(strings.TrimPrefix(raw, "Bearer ")), handler.cfg, handler.now())
	if err != nil {
		metadata.AuthResult = gateway.AuthResultInvalidToken
		reason := "invalid bearer token"
		metadata.RejectReason = &reason
		errorType := "auth_error"
		metadata.ErrorType = &errorType
		return nil, false
	}

	metadata.AuthResult = gateway.AuthResultSuccess
	metadata.UserID = claims.Subject
	metadata.Roles = claims.Roles
	return &identity{userID: claims.Subject, roles: claims.Roles}, true
}

// isPublicPath reports whether a route may bypass gateway JWT validation.
func isPublicPath(path string) bool {
	publicPaths := map[string]struct{}{
		"/ready":        {},
		"/docs":         {},
		"/redoc":        {},
		"/openapi.json": {},
	}
	if _, ok := publicPaths[path]; ok {
		return true
	}
	for _, prefix := range []string{
		"/api/v1/account/register-trial",
		"/api/v1/account/login",
		"/api/v1/account/send-verification-code",
		"/api/v1/account/leads",
	} {
		if strings.HasPrefix(path, prefix) {
			return true
		}
	}
	return false
}
