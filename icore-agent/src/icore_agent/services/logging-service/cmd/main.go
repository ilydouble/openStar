package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	applogging "xiehe-logging-service/internal/application/logging"
	"xiehe-logging-service/internal/config"
	"xiehe-logging-service/internal/infrastructure/filesink"
	kafkapub "xiehe-logging-service/internal/infrastructure/kafka"
	"xiehe-logging-service/internal/interfaces/console"
	httpapi "xiehe-logging-service/internal/interfaces/http"
	"xiehe-services-lib-go/httpserver"
)

const kafkaStartupCheckTimeout = 10 * time.Second

// main wires configuration, sinks, Kafka publishing, and the HTTP server lifecycle.
func main() {
	cfg := config.Load()
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	publisher := kafkapub.NewPublisher(cfg.KafkaBrokers, cfg.KafkaTopic)
	checkCtx, cancelCheck := context.WithTimeout(ctx, kafkaStartupCheckTimeout)
	if err := publisher.Check(checkCtx); err != nil {
		cancelCheck()
		log.Panicf(
			"kafka startup check failed for brokers=%v topic=%q: %v",
			cfg.KafkaBrokers,
			cfg.KafkaTopic,
			err,
		)
	}
	cancelCheck()
	defer func() {
		if err := publisher.Close(); err != nil {
			log.Printf("kafka publisher close failed: %v", err)
		}
	}()

	service := applogging.NewService(
		applogging.Config{
			FlushInterval: cfg.FlushInterval,
			QueueSize:     cfg.QueueSize,
			MaxBatchSize:  cfg.MaxBatchSize,
		},
		[]applogging.BatchSink{
			&console.Sink{Writer: os.Stdout, Color: cfg.ConsoleColor},
			filesink.New(cfg.SpoolFile, filesink.AllEvents),
			filesink.New(cfg.ErrorAuditFile, filesink.ErrorAndAuditOnly),
		},
		publisher,
	)
	service.Start(ctx)

	handler := httpapi.NewHandler(service, cfg.ServiceToken)
	server := httpserver.New(cfg.HTTPServerConfig(), httpapi.NewRouter(handler))

	go func() {
		<-ctx.Done()
		shutdownCtx, cancel := context.WithTimeout(context.Background(), cfg.ShutdownTimeout)
		defer cancel()
		if err := server.Shutdown(shutdownCtx); err != nil {
			log.Printf("logging-service shutdown failed: %v", err)
		}
	}()

	log.Printf("logging-service listening on %s", cfg.Addr)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatal(err)
	}
}
