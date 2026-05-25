package jwt

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"icore-gateway/internal/domain/identity"
	"strings"
	"time"
)

// Config contains the JWT validation settings consumed by the gateway.
type Config struct {
	Secret   string
	Issuer   string
	Audience string
}

// Authenticator validates HS256 access tokens issued by icore-agent.
type Authenticator struct {
	config Config
}

// NewAuthenticator creates a JWT authenticator for gateway protected routes.
func NewAuthenticator(config Config) *Authenticator {
	return &Authenticator{config: config}
}

// Authenticate validates a bearer token and returns the trusted upstream identity.
func (auth *Authenticator) Authenticate(token string, now time.Time) (identity.Identity, error) {
	claims, err := validateJWT(token, auth.config, now)
	if err != nil {
		return identity.Identity{}, err
	}
	return identity.Identity{UserID: claims.Subject, Roles: claims.Roles}, nil
}

type claims struct {
	Subject  string   `json:"sub"`
	Roles    []string `json:"roles"`
	Issuer   string   `json:"iss"`
	Audience string   `json:"aud"`
	IssuedAt int64    `json:"iat"`
	Expires  int64    `json:"exp"`
}

func validateJWT(token string, config Config, now time.Time) (claims, error) {
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return claims{}, errors.New("token must have three JWT segments")
	}

	signingInput := parts[0] + "." + parts[1]
	digest := hmac.New(sha256.New, []byte(config.Secret))
	_, _ = digest.Write([]byte(signingInput))
	expected := base64.RawURLEncoding.EncodeToString(digest.Sum(nil))
	if !hmac.Equal([]byte(parts[2]), []byte(expected)) {
		return claims{}, errors.New("invalid token signature")
	}

	var header struct {
		Algorithm string `json:"alg"`
	}
	if err := decodeSegment(parts[0], &header); err != nil {
		return claims{}, err
	}
	if header.Algorithm != "HS256" {
		return claims{}, errors.New("unsupported token algorithm")
	}

	var tokenClaims claims
	if err := decodeSegment(parts[1], &tokenClaims); err != nil {
		return claims{}, err
	}
	if err := tokenClaims.validate(config, now); err != nil {
		return claims{}, err
	}
	return tokenClaims, nil
}

func (tokenClaims claims) validate(config Config, now time.Time) error {
	if strings.TrimSpace(tokenClaims.Subject) == "" {
		return errors.New("subject claim is required")
	}
	if tokenClaims.Issuer != config.Issuer {
		return errors.New("issuer claim is invalid")
	}
	if tokenClaims.Audience != config.Audience {
		return errors.New("audience claim is invalid")
	}
	if tokenClaims.Expires <= 0 || now.Unix() >= tokenClaims.Expires {
		return errors.New("token expired")
	}
	for _, role := range tokenClaims.Roles {
		if strings.TrimSpace(role) == "" {
			return errors.New("roles claim is invalid")
		}
	}
	return nil
}

func decodeSegment(segment string, target any) error {
	raw, err := base64.RawURLEncoding.DecodeString(segment)
	if err != nil {
		return err
	}
	return json.Unmarshal(raw, target)
}
