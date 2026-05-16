package router

import (
	"net/http"

	"github.com/go-chi/chi/v5"

	"icore-gateway/internal/gateway"
	"icore-gateway/internal/gateway/handler"
)

// NewRouter builds the chi gateway router with health and proxy routes.
func NewRouter(cfg gateway.Config, deps gateway.Dependencies) http.Handler {
	handlers := handler.New(cfg, deps)

	router := chi.NewRouter()
	router.Get("/health", handlers.HandleHealth)
	router.Handle("/*", http.HandlerFunc(handlers.HandleProxy))
	return router
}
