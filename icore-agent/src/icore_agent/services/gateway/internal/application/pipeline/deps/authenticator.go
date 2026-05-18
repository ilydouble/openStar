package deps

import (
	domain2 "icore-gateway/internal/domain/identity"
	"time"
)

// Authenticator validates bearer tokens and returns an upstream identity.
type Authenticator interface {
	Authenticate(token string, now time.Time) (domain2.Identity, error)
}
