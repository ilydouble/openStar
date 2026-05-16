package main

import (
	"context"
	"log"
	"net/http"
	"os/signal"
	"syscall"
	"time"

	"github.com/redis/go-redis/v9"

	"icore-gateway/internal/config"
	"icore-gateway/internal/gateway"
	httpserver "icore-services-lib-go/http/server"
)

// main wires configuration, Redis rate limiting, logging, and the HTTP server lifecycle.
func main() {
	cfg := config.Load()
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	redisOptions, err := redis.ParseURL(cfg.RedisURL)
	if err != nil {
		log.Fatalf("invalid REDIS_URL: %v", err)
	}
	timeLocation, err := cfg.TimeLocation()
	if err != nil {
		log.Fatalf("invalid GATEWAY_TIME_ZONE %q: %v", cfg.TimeZone, err)
	}
	redisClient := redis.NewClient(redisOptions)
	defer redisClient.Close()

	router := gateway.NewRouter(
		gateway.Config{
			BackendURL:           cfg.BackendURL,
			JWTSecret:            cfg.JWTSecret,
			JWTIssuer:            cfg.JWTIssuer,
			JWTAudience:          cfg.JWTAudience,
			LoggingServiceName:   cfg.LoggingServiceName,
			RateLimitWindowLimit: cfg.RateLimitWindowLimit,
			TimeLocation:         timeLocation,
		},
		gateway.Dependencies{
			Logger: gateway.NewHTTPLogger(
				cfg.LoggingServiceURL,
				cfg.LoggingServiceToken,
				cfg.LoggingServiceTimeout,
			),
			Limiter: gateway.NewRedisLimiter(
				redisClient,
				cfg.RateLimitWindowLimit,
				cfg.RateLimitWindow,
				cfg.RateLimitKeyPrefix,
				time.Now,
			),
			Now: time.Now,
		},
	)
	server := httpserver.New(cfg.HTTPServerConfig(), router)

	go func() {
		<-ctx.Done()
		shutdownCtx, cancel := context.WithTimeout(context.Background(), cfg.ShutdownTimeout)
		defer cancel()
		if err := server.Shutdown(shutdownCtx); err != nil {
			log.Printf("gateway shutdown failed: %v", err)
		}
	}()

	log.Printf("icore-gateway listening on %s", cfg.Addr)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatal(err)
	}
}
