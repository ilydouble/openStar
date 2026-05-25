package jwt

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"testing"
	"time"
)

func TestAuthenticatorValidatesHS256JWT(t *testing.T) {
	secret := "test-secret-with-at-least-32-bytes"
	now := time.Date(2026, 5, 16, 15, 30, 0, 0, time.UTC)
	token := signTestJWT(t, secret, map[string]any{
		"sub":   "user-1",
		"roles": []string{"owner", "admin"},
		"iss":   "icore-agent",
		"aud":   "icore-gateway",
		"iat":   now.Add(-time.Minute).Unix(),
		"exp":   now.Add(time.Hour).Unix(),
	})

	identity, err := NewAuthenticator(Config{
		Secret:   secret,
		Issuer:   "icore-agent",
		Audience: "icore-gateway",
	}).Authenticate(token, now)
	if err != nil {
		t.Fatalf("authenticate: %v", err)
	}

	if identity.UserID != "user-1" {
		t.Fatalf("user id = %q, want user-1", identity.UserID)
	}
	if got := identity.Roles; len(got) != 2 || got[0] != "owner" || got[1] != "admin" {
		t.Fatalf("roles = %#v, want owner/admin", got)
	}
}

func TestAuthenticatorRejectsExpiredJWT(t *testing.T) {
	now := time.Date(2026, 5, 16, 15, 30, 0, 0, time.UTC)
	token := signTestJWT(t, "secret", map[string]any{
		"sub":   "user-1",
		"roles": []string{"owner"},
		"iss":   "icore-agent",
		"aud":   "icore-gateway",
		"iat":   now.Add(-time.Hour).Unix(),
		"exp":   now.Add(-time.Minute).Unix(),
	})

	_, err := NewAuthenticator(Config{
		Secret:   "secret",
		Issuer:   "icore-agent",
		Audience: "icore-gateway",
	}).Authenticate(token, now)
	if err == nil {
		t.Fatal("expected expired token error")
	}
}

func signTestJWT(t *testing.T, secret string, claims map[string]any) string {
	t.Helper()
	header, err := json.Marshal(map[string]string{"alg": "HS256", "typ": "JWT"})
	if err != nil {
		t.Fatalf("marshal header: %v", err)
	}
	payload, err := json.Marshal(claims)
	if err != nil {
		t.Fatalf("marshal claims: %v", err)
	}
	headerSegment := base64.RawURLEncoding.EncodeToString(header)
	payloadSegment := base64.RawURLEncoding.EncodeToString(payload)
	signingInput := headerSegment + "." + payloadSegment
	digest := hmac.New(sha256.New, []byte(secret))
	_, _ = digest.Write([]byte(signingInput))
	return signingInput + "." + base64.RawURLEncoding.EncodeToString(digest.Sum(nil))
}
