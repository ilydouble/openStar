package api

import (
	"encoding/json"
	"net/http"
	"time"
)

// WriteJSON wraps successful payloads in the API envelope shared by Go services.
func WriteJSON(w http.ResponseWriter, status int, payload any) {
	message := "操作成功"
	if status >= http.StatusBadRequest {
		message = "请求失败"
	}

	writeEnvelope(w, status, ApiEnvelope{
		Code:      status,
		Message:   message,
		Data:      payload,
		Timestamp: time.Now().UTC().Format(time.RFC3339Nano),
	})
}

// WriteError wraps API errors in the shared envelope.
func WriteError(w http.ResponseWriter, status int, message string) {
	writeEnvelope(w, status, ApiEnvelope{
		Code:      status,
		Message:   message,
		Data:      nil,
		Timestamp: time.Now().UTC().Format(time.RFC3339Nano),
	})
}

func writeEnvelope(w http.ResponseWriter, status int, payload ApiEnvelope) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}
