package gateway

import (
	"time"

	sharedlogging "icore-services-lib-go/logging"
)

// AccessLogMetadata is the gateway metadata object stored under logging-service metadata.
type AccessLogMetadata struct {
	RequestTimestamp   string   `json:"request_timestamp"`
	RequestID          string   `json:"request_id"`
	Method             string   `json:"method"`
	Path               string   `json:"path"`
	Query              string   `json:"query"`
	ClientIP           string   `json:"client_ip"`
	AuthResult         string   `json:"auth_result"`
	UserAgent          string   `json:"user_agent"`
	UserID             string   `json:"user_id"`
	Roles              []string `json:"roles"`
	UpstreamService    *string  `json:"upstream_service"`
	UpstreamAddr       *string  `json:"upstream_addr"`
	UpstreamStatusCode *int     `json:"upstream_status_code"`
	FinalStatusCode    int      `json:"final_status_code"`
	RequestElapsedTime int64    `json:"request_elapsed_time"`
	ErrorType          *string  `json:"error_type"`
	RateLimitResult    string   `json:"rate_limit_result"`
	RejectReason       *string  `json:"reject_reason"`
}

// AccessLogEvent is the domain event emitted after a gateway request lifecycle.
type AccessLogEvent struct {
	Timestamp time.Time
	Level     sharedlogging.LogLevel
	Service   string
	Message   string
	TraceID   string
	Metadata  AccessLogMetadata
}

// ToLogEvent converts a gateway access log event to the logging-service contract.
func (event AccessLogEvent) ToLogEvent() sharedlogging.LogEvent {
	return sharedlogging.LogEvent{
		Timestamp: event.Timestamp,
		Level:     event.Level,
		Service:   event.Service,
		Message:   event.Message,
		TraceID:   event.TraceID,
		Metadata:  event.Metadata,
	}
}
