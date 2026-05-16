package handler

import (
	"context"
	"log"
	"net/http"
	"time"

	"icore-gateway/internal/gateway"
	sharedlogging "icore-services-lib-go/logging"
)

// emitLog finalizes request metadata and sends one gateway access event.
func (handler *Handler) emitLog(ctx context.Context, start time.Time, metadata *gateway.GatewayMetadata, recorder *statusRecorder) {
	metadata.FinalStatusCode = recorder.Status()
	metadata.RequestElapsedTime = handler.now().Sub(start).Milliseconds()
	if metadata.FinalStatusCode >= http.StatusInternalServerError {
		errorType := "upstream_error"
		metadata.ErrorType = &errorType
	}
	if handler.logger == nil {
		return
	}

	level := sharedlogging.LogLevelInfo
	if metadata.FinalStatusCode >= http.StatusInternalServerError {
		level = sharedlogging.LogLevelError
	} else if metadata.FinalStatusCode >= http.StatusBadRequest {
		level = sharedlogging.LogLevelWarning
	}
	event := sharedlogging.LogEvent{
		Timestamp: start,
		Level:     level,
		Service:   handler.cfg.LoggingServiceName,
		Message:   "gateway request",
		TraceID:   metadata.RequestID,
		Metadata:  *metadata,
	}
	if err := handler.logger.Emit(ctx, event); err != nil {
		log.Printf("gateway log emit failed: %v", err)
	}
}
