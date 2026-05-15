package gateway

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"strings"
	"time"
)

// Claims contains the JWT identity fields consumed by the gateway.
type Claims struct {
	Subject  string   `json:"sub"`
	Roles    []string `json:"roles"`
	Issuer   string   `json:"iss"`
	Audience string   `json:"aud"`
	IssuedAt int64    `json:"iat"`
	Expires  int64    `json:"exp"`
}

// ValidateJWT verifies an HS256 access token issued by icore-agent.
func ValidateJWT(token string, cfg Config, now time.Time) (Claims, error) {
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return Claims{}, errors.New("token must have three JWT segments")
	}

	signingInput := parts[0] + "." + parts[1]
	digest := hmac.New(sha256.New, []byte(cfg.JWTSecret))
	_, _ = digest.Write([]byte(signingInput))
	expected := base64.RawURLEncoding.EncodeToString(digest.Sum(nil))
	if !hmac.Equal([]byte(parts[2]), []byte(expected)) {
		return Claims{}, errors.New("invalid token signature")
	}

	var header struct {
		Algorithm string `json:"alg"`
	}
	if err := decodeSegment(parts[0], &header); err != nil {
		return Claims{}, err
	}
	if header.Algorithm != "HS256" {
		return Claims{}, errors.New("unsupported token algorithm")
	}

	var claims Claims
	if err := decodeSegment(parts[1], &claims); err != nil {
		return Claims{}, err
	}
	if err := claims.Validate(cfg, now); err != nil {
		return Claims{}, err
	}
	return claims, nil
}

// Validate checks the claims required by the gateway.
func (claims Claims) Validate(cfg Config, now time.Time) error {
	if strings.TrimSpace(claims.Subject) == "" {
		return errors.New("subject claim is required")
	}
	if claims.Issuer != cfg.JWTIssuer {
		return errors.New("issuer claim is invalid")
	}
	if claims.Audience != cfg.JWTAudience {
		return errors.New("audience claim is invalid")
	}
	if claims.Expires <= 0 || now.Unix() >= claims.Expires {
		return errors.New("token expired")
	}
	for _, role := range claims.Roles {
		if strings.TrimSpace(role) == "" {
			return errors.New("roles claim is invalid")
		}
	}
	return nil
}

// decodeSegment decodes one base64url JWT segment into target.
func decodeSegment(segment string, target any) error {
	raw, err := base64.RawURLEncoding.DecodeString(segment)
	if err != nil {
		return err
	}
	return json.Unmarshal(raw, target)
}
