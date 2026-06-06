package proxy

import (
	"net/http"
	"net/http/httputil"
	"net/url"

	sharedhttp "icore-services-lib-go/http/api"
)

// ReverseProxy forwards gateway traffic to one configured upstream service.
type ReverseProxy struct {
	defaultBackendURL string
	transport         http.RoundTripper
}

// NewReverseProxy creates a reverse proxy for the configured backend URL.
func NewReverseProxy(backendURL string, transport http.RoundTripper) *ReverseProxy {
	return &ReverseProxy{defaultBackendURL: backendURL, transport: transport}
}

func (proxy *ReverseProxy) newUpstreamProxy(upstreamURL string) *httputil.ReverseProxy {
	backend, err := url.Parse(upstreamURL)
	if err != nil {
		panic(err)
	}
	upstreamProxy := httputil.NewSingleHostReverseProxy(backend)
	if proxy.transport != nil {
		upstreamProxy.Transport = proxy.transport
	}
	originalDirector := upstreamProxy.Director
	upstreamProxy.Director = func(req *http.Request) {
		originalDirector(req)
		req.Host = backend.Host
	}
	upstreamProxy.ErrorHandler = func(w http.ResponseWriter, _ *http.Request, _ error) {
		sharedhttp.WriteError(w, http.StatusBadGateway, "upstream unavailable")
	}
	return upstreamProxy
}

// ServeHTTP forwards the request to the configured upstream.
func (proxy *ReverseProxy) ServeHTTP(w http.ResponseWriter, r *http.Request, upstreamURL string) {
	if upstreamURL == "" {
		upstreamURL = proxy.defaultBackendURL
	}
	proxy.newUpstreamProxy(upstreamURL).ServeHTTP(w, r)
}
