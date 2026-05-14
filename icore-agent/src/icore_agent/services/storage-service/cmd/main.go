package main

import (
	"log"
	"net/http"

	"xiehe-services-lib-go/httpserver"
	appstorage "xiehe-storage-service/internal/application/storage"
	"xiehe-storage-service/internal/config"
	"xiehe-storage-service/internal/infrastructure/s3storage"
	httpapi "xiehe-storage-service/internal/interfaces/http"
)

func main() {
	cfg := config.Load()

	clients := s3storage.NewClients(cfg)
	repository := s3storage.NewRepository(clients.Internal, clients.Presign)
	service := appstorage.NewService(repository)
	handler := httpapi.NewHandler(
		service,
		cfg.ServiceToken,
		httpapi.WithMaxUploadBodyBytes(cfg.MaxUploadBodyBytes),
	)
	router := httpapi.NewRouter(handler)
	server := httpserver.New(cfg.HTTPServerConfig(), router)

	log.Printf("storage-service listening on %s", cfg.Addr)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatal(err)
	}
}
