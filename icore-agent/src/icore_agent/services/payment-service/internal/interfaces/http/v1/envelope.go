package httpv1

import (
	"encoding/json"
	"net/http"
	"time"

	sharedhttp "icore-services-lib-go/http/api"
)

// writeSuccess writes the shared ApiEnvelope success shape.
func writeSuccess(w http.ResponseWriter, status int, data any) {
	sharedhttp.WriteJSON(w, status, data)
}

// writeError writes the shared ApiEnvelope error shape.
func writeError(w http.ResponseWriter, status int, errorReason string, message string) {
	if message == "" {
		message = http.StatusText(status)
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(sharedhttp.ApiEnvelope{
		Code:        status,
		Message:     message,
		Data:        nil,
		Timestamp:   time.Now().UTC().Format(time.RFC3339Nano),
		ErrorReason: errorReason,
	})
}
