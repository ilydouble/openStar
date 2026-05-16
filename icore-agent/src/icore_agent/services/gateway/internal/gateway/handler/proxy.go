package handler

import (
	"net/http"
	"net/http/httputil"
	"strings"
)

// HandleProxy authenticates, rate-limits, and forwards requests to icore-agent.
func (handler *Handler) HandleProxy(w http.ResponseWriter, r *http.Request) {
	upstream := "icore-agent"
	metadata, start := handler.beginRequest(w, r, &upstream)
	recorder := newStatusRecorder(w)
	defer handler.emitLog(r.Context(), start, metadata, recorder)

	ident, ok := handler.authenticate(r, metadata)
	if !ok {
		writeJSON(recorder, http.StatusUnauthorized, map[string]string{"message": "unauthorized"})
		return
	}
	if ident != nil {
		r.Header.Set("X-User-ID", ident.userID)
		r.Header.Set("X-User-Roles", strings.Join(ident.roles, ","))
	}

	if !handler.allowRequest(r.Context(), metadata, upstream) {
		writeJSON(recorder, http.StatusTooManyRequests, map[string]string{"message": "rate limit exceeded"})
		return
	}

	handler.proxy.ServeHTTP(recorder, r)
	if recorder.status != 0 {
		status := recorder.status
		metadata.UpstreamStatusCode = &status
	}
}

// newProxy creates the reverse proxy used for icore-agent upstream traffic.
func (handler *Handler) newProxy() *httputil.ReverseProxy {
	proxy := httputil.NewSingleHostReverseProxy(handler.backend)
	if handler.transport != nil {
		proxy.Transport = handler.transport
	}
	originalDirector := proxy.Director
	proxy.Director = func(req *http.Request) {
		originalDirector(req)
		req.Host = handler.backend.Host
	}
	proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
		writeJSON(w, http.StatusBadGateway, map[string]string{"message": "upstream unavailable"})
	}
	return proxy
}
