package main

import (
	"context"
	"icore-gateway/internal/application/identity_policy"
	appgateway "icore-gateway/internal/application/pipeline"
	pipeline_deps "icore-gateway/internal/application/pipeline/deps"
	"icore-gateway/internal/application/route_policy"
	"icore-gateway/internal/domain/rate_limit"
	domain2 "icore-gateway/internal/domain/request_id"
	"log"
	"net/http"
	"os/signal"
	"syscall"
	"time"

	"github.com/redis/go-redis/v9"

	"icore-gateway/internal/config"
	jwtinfra "icore-gateway/internal/infrastructure/jwt"
	logginginfra "icore-gateway/internal/infrastructure/logging"
	proxyinfra "icore-gateway/internal/infrastructure/proxy"
	ratelimitinfra "icore-gateway/internal/infrastructure/rate_limiter"
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

	loggingClient := sharedlogging.NewLoggingServiceClient(
		sharedlogging.LoggingServiceClientConfig{
			BaseURL:   cfg.LoggingServiceURL,
			Token:     cfg.LoggingServiceToken,
			Timeout:   cfg.LoggingServiceTimeout,
			QueueSize: cfg.AccessLogQueueSize,
		},
	)
	accessLogger := logginginfra.NewGatewayAccessLogger(
		logginginfra.GatewayAccessLoggerConfig{
			Emitter: loggingClient,
		},
	)

	pipelineDependencies := pipeline_deps.PipelineDependencies{
		Authenticator: jwtinfra.NewAuthenticator(
			jwtinfra.Config{
				Secret:   cfg.JWTSecret,
				Issuer:   cfg.JWTIssuer,
				Audience: cfg.JWTAudience,
			},
		),
		ClientIPLimiter: ratelimitinfra.NewRedisLimiter(
			redisClient,
			ratelimitinfra.TokenBucketProfile{
				Scope:         rate_limit.RateLimitScopeClientIP,
				RatePerSecond: cfg.ClientIPRateLimit.RatePerSecond,
				Burst:         cfg.ClientIPRateLimit.Burst,
			},
			cfg.RateLimitKeyPrefix,
			time.Now,
		),
		UserIDLimiter: ratelimitinfra.NewRedisLimiter(
			redisClient,
			ratelimitinfra.TokenBucketProfile{
				Scope:         rate_limit.RateLimitScopeUserID,
				RatePerSecond: cfg.UserIDRateLimit.RatePerSecond,
				Burst:         cfg.UserIDRateLimit.Burst,
			},
			cfg.RateLimitKeyPrefix,
			time.Now,
		),
		ServiceLimiter: ratelimitinfra.NewRedisLimiter(
			redisClient,
			ratelimitinfra.TokenBucketProfile{
				Scope:         rate_limit.RateLimitScopeService,
				RatePerSecond: cfg.ServiceRateLimitProfile("icore-agent").RatePerSecond,
				Burst:         cfg.ServiceRateLimitProfile("icore-agent").Burst,
			},
			cfg.RateLimitKeyPrefix,
			time.Now,
		),
		Proxy:        proxyinfra.NewReverseProxy(cfg.BackendURL, nil),
		AccessLogger: accessLogger,
	}
	pipeline := appgateway.NewPipeline(
		appgateway.PipelineConfig{
			ServiceName:     cfg.LoggingServiceName,
			RoutePolicy:     route_policy.NewDefaultRoutePolicy(cfg.BackendURL),
			RequestIDPolicy: domain2.RequestIDPolicy{},
			IdentityPolicy:  identity_policy.IdentityPolicy{},
			Location:        timeLocation,
			Now:             time.Now,
		},
		pipelineDependencies,
	)
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
