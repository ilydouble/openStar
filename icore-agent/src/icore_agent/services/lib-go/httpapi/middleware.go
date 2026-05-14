package httpapi

import (
	"net/http"

	"github.com/gin-gonic/gin"
)

// TokenAuthConfig defines shared service-token authentication behavior.
type TokenAuthConfig struct {
	Header          string
	Token           string
	Message         string
	AllowEmptyToken bool
}

// TokenAuth validates a shared service-token header before continuing the route.
func TokenAuth(cfg TokenAuthConfig) gin.HandlerFunc {
	message := cfg.Message
	if message == "" {
		message = "unauthorized"
	}

	return func(ctx *gin.Context) {
		if cfg.Token == "" && cfg.AllowEmptyToken {
			ctx.Next()
			return
		}
		if ctx.GetHeader(cfg.Header) != cfg.Token {
			WriteError(ctx, http.StatusUnauthorized, message)
			return
		}
		ctx.Next()
	}
}
