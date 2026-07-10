package httpapi

import (
	"net/http"

	"github.com/go-chi/chi/v5"
)

// NewRouter builds the chi gateway router with edge CORS, health, and upstream routes.
func NewRouter(handler *Handler, corsConfig CORSConfig) http.Handler {
	router := chi.NewRouter()
	router.Use(CORSMiddleware(corsConfig))
	router.Get("/health", handler.HandleHealth)
	router.Handle("/*", http.HandlerFunc(handler.HandleProxy))
	return router
}
