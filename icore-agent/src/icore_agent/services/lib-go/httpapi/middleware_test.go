package httpapi

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestTokenAuthRejectsMissingToken(t *testing.T) {
	router := NewRouter()
	router.GET(
		"/protected",
		TokenAuth(TokenAuthConfig{
			Header:  "X-Service-Token",
			Token:   "secret",
			Message: "unauthorized",
		}),
		func(ctx *gin.Context) {
			WriteJSON(ctx, http.StatusOK, gin.H{"ok": true})
		},
	)

	response := httptest.NewRecorder()
	router.ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/protected", nil))

	if response.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d", response.Code)
	}
}

func TestTokenAuthAllowsMatchingToken(t *testing.T) {
	router := NewRouter()
	router.GET(
		"/protected",
		TokenAuth(TokenAuthConfig{
			Header:  "X-Service-Token",
			Token:   "secret",
			Message: "unauthorized",
		}),
		func(ctx *gin.Context) {
			WriteJSON(ctx, http.StatusOK, gin.H{"ok": true})
		},
	)

	request := httptest.NewRequest(http.MethodGet, "/protected", nil)
	request.Header.Set("X-Service-Token", "secret")
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", response.Code, response.Body.String())
	}
}

func TestTokenAuthCanAllowEmptyConfiguredToken(t *testing.T) {
	router := NewRouter()
	router.GET(
		"/protected",
		TokenAuth(TokenAuthConfig{
			Header:          "X-Service-Token",
			Token:           "",
			Message:         "unauthorized",
			AllowEmptyToken: true,
		}),
		func(ctx *gin.Context) {
			WriteJSON(ctx, http.StatusOK, gin.H{"ok": true})
		},
	)

	response := httptest.NewRecorder()
	router.ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/protected", nil))

	if response.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", response.Code, response.Body.String())
	}
}
