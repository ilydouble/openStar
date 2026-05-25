package proxy

import (
	"encoding/json"
	"net/http"
	"net/http/httputil"
	"net/url"
	"time"
)

// ReverseProxy forwards gateway traffic to one configured upstream service.
type ReverseProxy struct {
	proxy *httputil.ReverseProxy
}

// NewReverseProxy creates a reverse proxy for the configured backend URL.
func NewReverseProxy(backendURL string, transport http.RoundTripper) *ReverseProxy {
	backend, err := url.Parse(backendURL)
	if err != nil {
		panic(err)
	}
	proxy := httputil.NewSingleHostReverseProxy(backend)
	if transport != nil {
		proxy.Transport = transport
	}
	originalDirector := proxy.Director
	proxy.Director = func(req *http.Request) {
		originalDirector(req)
		req.Host = backend.Host
	}
	proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadGateway)
		_ = json.NewEncoder(w).Encode(map[string]any{
			"code":       http.StatusBadGateway,
			"message":    "upstream unavailable",
			"data":       nil,
			"error_code": http.StatusText(http.StatusBadGateway),
			"timestamp":  time.Now().UTC().Format(time.RFC3339Nano),
		})
	}
	return &ReverseProxy{proxy: proxy}
}

// ServeHTTP forwards the request to the configured upstream.
func (proxy *ReverseProxy) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	proxy.proxy.ServeHTTP(w, r)
}
