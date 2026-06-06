package api

// ApiEnvelope is the shared JSON response contract for Go service APIs.
type ApiEnvelope struct {
	Code        int    `json:"code"`
	Message     string `json:"message"`
	Data        any    `json:"data"`
	Timestamp   string `json:"timestamp"`
	ErrorReason string `json:"error_reason,omitempty"`
}
