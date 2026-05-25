package pipeline

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestWriteJSONUsesApiEnvelope verifies gateway local success responses.
func TestWriteJSONUsesApiEnvelope(t *testing.T) {
	recorder := httptest.NewRecorder()

	writeJSON(recorder, http.StatusOK, map[string]string{"status": "ok"})

	payload := decodeJSONResponse(t, recorder)
	if payload["code"] != float64(http.StatusOK) {
		t.Fatalf("code = %#v, want %d", payload["code"], http.StatusOK)
	}
	if payload["message"] != "操作成功" {
		t.Fatalf("message = %#v", payload["message"])
	}
	data, ok := payload["data"].(map[string]any)
	if !ok || data["status"] != "ok" {
		t.Fatalf("data = %#v", payload["data"])
	}
	if payload["timestamp"] == "" {
		t.Fatal("timestamp should be present")
	}
}

// TestWriteJSONErrorUsesApiEnvelope verifies gateway local error responses.
func TestWriteJSONErrorUsesApiEnvelope(t *testing.T) {
	recorder := httptest.NewRecorder()

	writeJSON(recorder, http.StatusUnauthorized, map[string]string{"message": "unauthorized"})

	payload := decodeJSONResponse(t, recorder)
	if payload["code"] != float64(http.StatusUnauthorized) {
		t.Fatalf("code = %#v, want %d", payload["code"], http.StatusUnauthorized)
	}
	if payload["message"] != "unauthorized" {
		t.Fatalf("message = %#v", payload["message"])
	}
	if payload["data"] != nil {
		t.Fatalf("data = %#v, want nil", payload["data"])
	}
	if payload["error_code"] != http.StatusText(http.StatusUnauthorized) {
		t.Fatalf("error_code = %#v", payload["error_code"])
	}
}

// decodeJSONResponse decodes a response recorder body for envelope assertions.
func decodeJSONResponse(t *testing.T, recorder *httptest.ResponseRecorder) map[string]any {
	t.Helper()
	var payload map[string]any
	if err := json.Unmarshal(recorder.Body.Bytes(), &payload); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	return payload
}
