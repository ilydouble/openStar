package main

import (
	"context"
	"log"
	"net/http"
	"os/signal"
	"syscall"
	"time"

	"github.com/redis/go-redis/v9"

	appgateway "icore-gateway/internal/application/gateway"
	"icore-gateway/internal/config"
	domain "icore-gateway/internal/domain/gateway"
	jwtinfra "icore-gateway/internal/infrastructure/jwt"
	logginginfra "icore-gateway/internal/infrastructure/logging"
	proxyinfra "icore-gateway/internal/infrastructure/proxy"
	ratelimitinfra "icore-gateway/internal/infrastructure/redisratelimit"
	httpapi "icore-gateway/internal/interfaces/http"
	httpserver "icore-services-lib-go/http/server"
	sharedlogging "icore-services-lib-go/logging"
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

	loggingClient := sharedlogging.NewLoggingServiceClient(sharedlogging.LoggingServiceClientConfig{
		BaseURL: cfg.LoggingServiceURL,
		Token:   cfg.LoggingServiceToken,
		Timeout: cfg.LoggingServiceTimeout,
	})
	accessLogger := logginginfra.NewAsyncAccessLogger(logginginfra.Config{
		Emitter:   loggingClient,
		Timeout:   cfg.LoggingServiceTimeout,
		QueueSize: cfg.AccessLogQueueSize,
	})
	pipeline := appgateway.NewPipeline(appgateway.PipelineConfig{
		ServiceName:     cfg.LoggingServiceName,
		RoutePolicy:     appgateway.NewDefaultRoutePolicy(cfg.BackendURL),
		RequestIDPolicy: domain.RequestIDPolicy{},
		IdentityPolicy:  appgateway.IdentityPolicy{},
		Location:        timeLocation,
		Now:             time.Now,
	}, appgateway.PipelineDependencies{
		Authenticator: jwtinfra.NewAuthenticator(jwtinfra.Config{
			Secret:   cfg.JWTSecret,
			Issuer:   cfg.JWTIssuer,
			Audience: cfg.JWTAudience,
		}),
		Limiter: ratelimitinfra.NewRedisLimiter(
			redisClient,
			cfg.RateLimitWindowLimit,
			cfg.RateLimitWindow,
			cfg.RateLimitKeyPrefix,
			time.Now,
		),
		Proxy:        proxyinfra.NewReverseProxy(cfg.BackendURL, nil),
		AccessLogger: accessLogger,
	})
	router := httpapi.NewRouter(httpapi.NewHandler(pipeline))
	server := httpserver.New(cfg.HTTPServerConfig(), router)

	go func() {
		<-ctx.Done()
		shutdownCtx, cancel := context.WithTimeout(context.Background(), cfg.ShutdownTimeout)
		defer cancel()
		if err := server.Shutdown(shutdownCtx); err != nil {
			log.Printf("gateway shutdown failed: %v", err)
		}
		if err := accessLogger.Close(shutdownCtx); err != nil {
			log.Printf("gateway access log drain failed: %v", err)
		}
	}()

	log.Printf("icore-gateway listening on %s", cfg.Addr)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatal(err)
	}
}
