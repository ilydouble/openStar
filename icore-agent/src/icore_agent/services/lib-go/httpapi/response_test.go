package httpapi

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestWriteJSONWrapsPayloadInApiEnvelope(t *testing.T) {
	router := NewRouter()
	router.GET("/ok", func(ctx *gin.Context) {
		WriteJSON(ctx, http.StatusCreated, gin.H{"accepted": 1})
	})

	response := httptest.NewRecorder()
	router.ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/ok", nil))

	if response.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d", response.Code)
	}
	if response.Header().Get("Content-Type") != "application/json; charset=utf-8" {
		t.Fatalf("unexpected content type %q", response.Header().Get("Content-Type"))
	}

	var payload map[string]any
	if err := json.Unmarshal(response.Body.Bytes(), &payload); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if payload["code"] != float64(http.StatusCreated) {
		t.Fatalf("unexpected code %#v", payload["code"])
	}
	if payload["message"] != "操作成功" {
		t.Fatalf("unexpected message %#v", payload["message"])
	}
	data, ok := payload["data"].(map[string]any)
	if !ok || data["accepted"] != float64(1) {
		t.Fatalf("unexpected data %#v", payload["data"])
	}
	if payload["timestamp"] == "" {
		t.Fatal("timestamp should be populated")
	}
}

func TestWriteErrorUsesSharedErrorEnvelope(t *testing.T) {
	router := NewRouter()
	router.GET("/fail", func(ctx *gin.Context) {
		WriteError(ctx, http.StatusUnauthorized, "invalid token")
	})

	response := httptest.NewRecorder()
	router.ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/fail", nil))

	if response.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d", response.Code)
	}

	var payload map[string]any
	if err := json.Unmarshal(response.Body.Bytes(), &payload); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if payload["code"] != float64(http.StatusUnauthorized) {
		t.Fatalf("unexpected code %#v", payload["code"])
	}
	if payload["message"] != "invalid token" {
		t.Fatalf("unexpected message %#v", payload["message"])
	}
	if payload["data"] != nil {
		t.Fatalf("unexpected data %#v", payload["data"])
	}
	if payload["error_code"] != http.StatusText(http.StatusUnauthorized) {
		t.Fatalf("unexpected error code %#v", payload["error_code"])
	}
	if payload["timestamp"] == "" {
		t.Fatal("timestamp should be populated")
	}
}
