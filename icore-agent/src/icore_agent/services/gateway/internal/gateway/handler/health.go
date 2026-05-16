package handler

import (
	"net/http"

	"icore-gateway/internal/gateway"
)

// HandleHealth reports gateway process health.
func (handler *Handler) HandleHealth(w http.ResponseWriter, r *http.Request) {
	metadata, start := handler.beginRequest(w, r, nil)
	recorder := newStatusRecorder(w)
	defer handler.emitLog(r.Context(), start, metadata, recorder)

	metadata.AuthResult = gateway.AuthResultPublic
	metadata.RateLimitResult = "skipped"
	writeJSON(recorder, http.StatusOK, map[string]string{"status": "ok", "service": handler.cfg.LoggingServiceName})
}
