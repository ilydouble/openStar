package httpapi

import (
	"net/http"

	applogging "xiehe-logging-service/internal/application/logging"
	domain "xiehe-logging-service/internal/domain/logging"
	sharedhttp "xiehe-services-lib-go/httpapi"
)

// Handler exposes the HTTP API used by backend services to emit log events.
type Handler struct {
	service      *applogging.Service
	serviceToken string
}

// NewHandler binds the application service and shared service token to HTTP handlers.
func NewHandler(service *applogging.Service, serviceToken string) *Handler {
	return &Handler{service: service, serviceToken: serviceToken}
}

// HandleHealth reports process liveness.
func (handler *Handler) HandleHealth(ctx *sharedhttp.Context) {
	sharedhttp.WriteJSON(ctx, http.StatusOK, map[string]string{"status": "ok"})
}

// HandleLogEvent accepts one LogEvent and enqueues it for batched processing.
func (handler *Handler) HandleLogEvent(ctx *sharedhttp.Context) {
	var request logEventIngestRequest
	if !sharedhttp.DecodeJSON(ctx, &request, sharedhttp.DefaultJSONBodyLimit) {
		return
	}

	if err := handler.service.Ingest(ctx.Request.Context(), []domain.LogEvent{request.Event}); err != nil {
		sharedhttp.WriteError(ctx, http.StatusBadRequest, err.Error())
		return
	}

	sharedhttp.WriteJSON(ctx, http.StatusOK, map[string]int{"accepted": 1})
}

// HandleLogEventBatch accepts multiple LogEvent records in one request.
func (handler *Handler) HandleLogEventBatch(ctx *sharedhttp.Context) {
	var request logEventBatchIngestRequest
	if !sharedhttp.DecodeJSON(ctx, &request, sharedhttp.DefaultJSONBodyLimit) {
		return
	}

	if err := handler.service.Ingest(ctx.Request.Context(), request.Events); err != nil {
		sharedhttp.WriteError(ctx, http.StatusBadRequest, err.Error())
		return
	}

	sharedhttp.WriteJSON(ctx, http.StatusOK, map[string]int{"accepted": len(request.Events)})
}
