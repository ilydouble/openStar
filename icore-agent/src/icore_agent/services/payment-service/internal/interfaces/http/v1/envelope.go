package httpv1

import (
	"encoding/json"
	"net/http"
	"time"
)

type envelope struct {
	Code      int     `json:"code"`
	Message   string  `json:"message"`
	Data      any     `json:"data"`
	Timestamp string  `json:"timestamp"`
	ErrorCode *string `json:"error_code,omitempty"`
}

// writeSuccess writes the shared ApiEnvelope success shape.
func writeSuccess(w http.ResponseWriter, status int, data any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(envelope{
		Code:      status,
		Message:   http.StatusText(status),
		Data:      data,
		Timestamp: time.Now().UTC().Format(time.RFC3339Nano),
	})
}

// writeError writes the shared ApiEnvelope error shape.
func writeError(w http.ResponseWriter, status int, errorCode string, message string) {
	if message == "" {
		message = http.StatusText(status)
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(envelope{
		Code:      status,
		Message:   message,
		Data:      nil,
		Timestamp: time.Now().UTC().Format(time.RFC3339Nano),
		ErrorCode: &errorCode,
	})
}
