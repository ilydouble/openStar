package api

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestTokenAuthRejectsMissingToken(t *testing.T) {
	router := NewRouter()
	router.Get(
		"/protected",
		TokenAuth(TokenAuthConfig{
			Header:  "X-Service-Token",
			Token:   "secret",
			Message: "unauthorized",
		})(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			WriteJSON(w, http.StatusOK, map[string]bool{"ok": true})
		})).ServeHTTP,
	)

	response := httptest.NewRecorder()
	router.ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/protected", nil))

	if response.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d", response.Code)
	}
}

func TestTokenAuthAllowsMatchingToken(t *testing.T) {
	router := NewRouter()
	router.Get(
		"/protected",
		TokenAuth(TokenAuthConfig{
			Header:  "X-Service-Token",
			Token:   "secret",
			Message: "unauthorized",
		})(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			WriteJSON(w, http.StatusOK, map[string]bool{"ok": true})
		})).ServeHTTP,
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
	router.Get(
		"/protected",
		TokenAuth(TokenAuthConfig{
			Header:          "X-Service-Token",
			Token:           "",
			Message:         "unauthorized",
			AllowEmptyToken: true,
		})(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			WriteJSON(w, http.StatusOK, map[string]bool{"ok": true})
		})).ServeHTTP,
	)

	response := httptest.NewRecorder()
	router.ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/protected", nil))

	if response.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", response.Code, response.Body.String())
	}
}
