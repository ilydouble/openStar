package httpapi

import (
	"net/http"
	"strings"

	sharedhttp "icore-services-lib-go/http/api"
)

const (
	corsAllowMethods  = "GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS"
	corsExposeHeaders = "X-Request-ID"
	corsMaxAge        = "600"
)

var corsMethods = map[string]struct{}{
	http.MethodGet:     {},
	http.MethodHead:    {},
	http.MethodPost:    {},
	http.MethodPut:     {},
	http.MethodPatch:   {},
	http.MethodDelete:  {},
	http.MethodOptions: {},
}

// CORSConfig defines the browser origins accepted by the public gateway edge.
type CORSConfig struct {
	AllowedOrigins []string
}

// CORSMiddleware handles browser CORS at the gateway before auth and rate limiting.
func CORSMiddleware(config CORSConfig) func(http.Handler) http.Handler {
	allowedOrigins := allowedOriginSet(config.AllowedOrigins)
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			origin := strings.TrimSpace(r.Header.Get("Origin"))
			if origin == "" {
				next.ServeHTTP(w, r)
				return
			}
			preflight := isCORSPreflight(r)
			appendVary(w.Header(), "Origin")
			if preflight {
				appendVary(w.Header(), "Access-Control-Request-Method")
				appendVary(w.Header(), "Access-Control-Request-Headers")
			}

			_, originAllowed := allowedOrigins[origin]
			if !originAllowed {
				if preflight {
					sharedhttp.WriteError(w, http.StatusForbidden, "CORS origin is not allowed")
					return
				}
				next.ServeHTTP(w, r)
				return
			}

			setCORSResponseHeaders(w.Header(), origin)
			if !preflight {
				next.ServeHTTP(w, r)
				return
			}

			method := strings.ToUpper(strings.TrimSpace(r.Header.Get("Access-Control-Request-Method")))
			if _, methodAllowed := corsMethods[method]; !methodAllowed {
				sharedhttp.WriteError(w, http.StatusMethodNotAllowed, "CORS method is not allowed")
				return
			}

			w.Header().Set("Access-Control-Allow-Methods", corsAllowMethods)
			if requestedHeaders := strings.TrimSpace(r.Header.Get("Access-Control-Request-Headers")); requestedHeaders != "" {
				w.Header().Set("Access-Control-Allow-Headers", requestedHeaders)
			}
			w.Header().Set("Access-Control-Max-Age", corsMaxAge)
			w.WriteHeader(http.StatusNoContent)
		})
	}
}

// allowedOriginSet normalizes configured exact-match origins and rejects wildcards.
func allowedOriginSet(origins []string) map[string]struct{} {
	allowed := make(map[string]struct{}, len(origins))
	for _, origin := range origins {
		normalized := strings.TrimSpace(origin)
		if normalized == "" || normalized == "*" {
			continue
		}
		allowed[normalized] = struct{}{}
	}
	return allowed
}

// isCORSPreflight identifies browser preflight rather than arbitrary OPTIONS traffic.
func isCORSPreflight(r *http.Request) bool {
	return r.Method == http.MethodOptions &&
		strings.TrimSpace(r.Header.Get("Origin")) != "" &&
		strings.TrimSpace(r.Header.Get("Access-Control-Request-Method")) != ""
}

// setCORSResponseHeaders applies headers shared by actual and preflight responses.
func setCORSResponseHeaders(header http.Header, origin string) {
	header.Set("Access-Control-Allow-Origin", origin)
	header.Set("Access-Control-Allow-Credentials", "true")
	header.Set("Access-Control-Expose-Headers", corsExposeHeaders)
	appendVary(header, "Origin")
}

// appendVary adds one Vary token without duplicating an existing token.
func appendVary(header http.Header, value string) {
	for _, line := range header.Values("Vary") {
		for _, token := range strings.Split(line, ",") {
			if strings.EqualFold(strings.TrimSpace(token), value) {
				return
			}
		}
	}
	header.Add("Vary", value)
}
