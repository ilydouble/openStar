package httpapi

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestDecodeJSONReadsBoundedRequestBody(t *testing.T) {
	router := NewRouter()
	router.POST("/decode", func(ctx *gin.Context) {
		var request struct {
			Name string `json:"name"`
		}
		if !DecodeJSON(ctx, &request, 1024) {
			return
		}
		WriteJSON(ctx, http.StatusOK, gin.H{"name": request.Name})
	})

	response := httptest.NewRecorder()
	router.ServeHTTP(
		response,
		httptest.NewRequest(http.MethodPost, "/decode", strings.NewReader(`{"name":"alice"}`)),
	)

	if response.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", response.Code, response.Body.String())
	}
	if !strings.Contains(response.Body.String(), `"name":"alice"`) {
		t.Fatalf("unexpected response body %s", response.Body.String())
	}
}

func TestDecodeJSONRejectsBodiesOverLimit(t *testing.T) {
	router := NewRouter()
	router.POST("/decode", func(ctx *gin.Context) {
		var request struct {
			Name string `json:"name"`
		}
		if !DecodeJSON(ctx, &request, 4) {
			return
		}
		WriteJSON(ctx, http.StatusOK, gin.H{"name": request.Name})
	})

	response := httptest.NewRecorder()
	router.ServeHTTP(
		response,
		httptest.NewRequest(http.MethodPost, "/decode", strings.NewReader(`{"name":"alice"}`)),
	)

	if response.Code != http.StatusRequestEntityTooLarge {
		t.Fatalf("expected 413, got %d: %s", response.Code, response.Body.String())
	}
}
