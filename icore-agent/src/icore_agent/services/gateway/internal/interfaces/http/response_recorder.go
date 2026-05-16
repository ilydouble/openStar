package httpapi

import "net/http"

// ResponseRecorder captures the final response status while preserving HTTP interfaces.
type ResponseRecorder struct {
	http.ResponseWriter
	status int
}

// NewResponseRecorder wraps a ResponseWriter for gateway pipeline status capture.
func NewResponseRecorder(w http.ResponseWriter) *ResponseRecorder {
	return &ResponseRecorder{ResponseWriter: w}
}

// Unwrap exposes the underlying ResponseWriter to net/http response controllers.
func (recorder *ResponseRecorder) Unwrap() http.ResponseWriter {
	return recorder.ResponseWriter
}

// Flush forwards streaming flushes for SSE and other long-lived responses.
func (recorder *ResponseRecorder) Flush() {
	if flusher, ok := recorder.ResponseWriter.(http.Flusher); ok {
		flusher.Flush()
	}
}

// WriteHeader records the final HTTP response status.
func (recorder *ResponseRecorder) WriteHeader(status int) {
	recorder.status = status
	recorder.ResponseWriter.WriteHeader(status)
}

// Write records an implicit 200 status before writing the body.
func (recorder *ResponseRecorder) Write(data []byte) (int, error) {
	if recorder.status == 0 {
		recorder.status = http.StatusOK
	}
	return recorder.ResponseWriter.Write(data)
}

// Status returns the recorded status, defaulting to 200 for untouched responses.
func (recorder *ResponseRecorder) Status() int {
	if recorder.status == 0 {
		return http.StatusOK
	}
	return recorder.status
}
