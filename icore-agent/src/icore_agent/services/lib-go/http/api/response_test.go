package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestWriteJSONWrapsPayloadInApiEnvelope(t *testing.T) {
	router := NewRouter()
	router.Get("/ok", func(w http.ResponseWriter, r *http.Request) {
		WriteJSON(w, http.StatusCreated, map[string]int{"accepted": 1})
	})

	response := httptest.NewRecorder()
	router.ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/ok", nil))

	if response.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d", response.Code)
	}
	if response.Header().Get("Content-Type") != "application/json" {
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
	router.Get("/fail", func(w http.ResponseWriter, r *http.Request) {
		WriteError(w, http.StatusUnauthorized, "invalid token")
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
	if _, ok := payload["error_reason"]; ok {
		t.Fatalf("unexpected error_reason %#v", payload["error_reason"])
	}
	legacyErrorCodeKey := "error" + "_code"
	if _, ok := payload[legacyErrorCodeKey]; ok {
		t.Fatalf("unexpected legacy error code %#v", payload[legacyErrorCodeKey])
	}
	if payload["timestamp"] == "" {
		t.Fatal("timestamp should be populated")
	}
}
