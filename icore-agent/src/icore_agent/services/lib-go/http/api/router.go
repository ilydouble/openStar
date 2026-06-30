package api

import "github.com/go-chi/chi/v5"

// Router is the Chi mux type used by service entrypoints.
type Router = chi.Mux

// NewRouter returns a Chi router with no request logger.
func NewRouter() *Router {
	return chi.NewRouter()
}
