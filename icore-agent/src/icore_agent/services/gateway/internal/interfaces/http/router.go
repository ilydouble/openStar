package httpapi

import (
	"net/http"

	"github.com/go-chi/chi/v5"
)

// NewRouter builds the chi gateway router with local health and upstream routes.
func NewRouter(handler *Handler) http.Handler {
	router := chi.NewRouter()
	router.Get("/health", handler.HandleHealth)
	router.Handle("/*", http.HandlerFunc(handler.HandleProxy))
	return router
}
