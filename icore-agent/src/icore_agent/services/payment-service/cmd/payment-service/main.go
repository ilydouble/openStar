package main

import (
	"context"
	"log"
	"net/http"
	"os/signal"
	"syscall"
	"time"

	"icore-payment-service/internal/application/checkout"
	"icore-payment-service/internal/application/notification"
	"icore-payment-service/internal/config"
	outboxkafka "icore-payment-service/internal/infrastructure/kafka"
	postgresrepo "icore-payment-service/internal/infrastructure/persistence/postgres"
	"icore-payment-service/internal/infrastructure/wechatpay"
	httpv1 "icore-payment-service/internal/interfaces/http/v1"
	httpserver "icore-services-lib-go/http/server"
	sharedlogging "icore-services-lib-go/logging"
	sharedkafka "icore-services-lib-go/mq/kafka"
)

// main wires payment-service configuration, persistence, provider adapters, and HTTP server lifecycle.
func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("invalid payment-service config: %v", err)
	}

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	loggingClient := sharedlogging.NewLoggingServiceClient(sharedlogging.LoggingServiceClientConfig{
		BaseURL:   cfg.LoggingServiceURL,
		Token:     cfg.LoggingServiceToken,
		Timeout:   cfg.LoggingServiceTimeout,
		QueueSize: cfg.LoggingQueueSize,
	})
	appLogger := sharedlogging.NewAppLogger(sharedlogging.AppLoggerConfig{
		Service: cfg.LoggingServiceName,
		Emitter: loggingClient,
	})

	db, err := postgresrepo.Open(ctx, postgresrepo.DBConfig{
		DatabaseURL:     cfg.DatabaseURL,
		MaxOpenConns:    cfg.DBMaxOpenConns,
		MaxIdleConns:    cfg.DBMaxIdleConns,
		ConnMaxLifetime: cfg.DBConnMaxLifetime,
	})
	if err != nil {
		log.Fatalf("connect payment database: %v", err)
	}
	defer db.Close()

	repository := postgresrepo.NewRepository(db, cfg.Catalog, time.Now)
	wechatProvider, err := wechatpay.NewNativeProvider(ctx, cfg.WeChatPay)
	if err != nil {
		log.Fatalf("initialize wechatpay native provider: %v", err)
	}

	checkoutService := checkout.NewService(checkout.ServiceConfig{
		Catalog:    cfg.Catalog,
		Repository: repository,
		Provider:   wechatProvider,
		Logger:     appLogger,
		AppID:      cfg.WeChatPay.AppID,
		MchID:      cfg.WeChatPay.MchID,
		NotifyURL:  cfg.WeChatPay.NotifyURL,
		OrderTTL:   cfg.OrderTTL,
	})
	notificationService := notification.NewService(notification.ServiceConfig{
		AppID:      cfg.WeChatPay.AppID,
		MchID:      cfg.WeChatPay.MchID,
		Provider:   wechatProvider,
		Repository: repository,
		Logger:     appLogger,
	})

	kafkaProducer := sharedkafka.NewKafkaPublisher(sharedkafka.Config{
		Brokers: cfg.KafkaBrokers,
		Topic:   cfg.KafkaTopic,
	})
	checkCtx, cancelCheck := context.WithTimeout(ctx, cfg.KafkaCheckTimeout)
	if err := kafkaProducer.Check(checkCtx); err != nil {
		cancelCheck()
		log.Fatalf("payment-service kafka startup check failed for brokers=%v topic=%q: %v", cfg.KafkaBrokers, cfg.KafkaTopic, err)
	}
	cancelCheck()
	defer kafkaProducer.Close()
	outboxPublisher := outboxkafka.NewPublisherWithConfig(repository, kafkaProducer, outboxkafka.PublisherConfig{
		BatchSize:      cfg.OutboxBatchSize,
		PublishTimeout: cfg.OutboxPublishTimeout,
		Logger:         log.Default(),
	})
	go outboxPublisher.Run(ctx, cfg.OutboxPollInterval)

	router := httpv1.NewRouter(httpv1.HandlerConfig{
		Checkout:     checkoutService,
		Notification: notificationService,
		ReadyCheck: func(ctx context.Context) error {
			if err := repository.Check(ctx); err != nil {
				return err
			}
			checkCtx, cancel := context.WithTimeout(ctx, cfg.KafkaCheckTimeout)
			defer cancel()
			return kafkaProducer.Check(checkCtx)
		},
	})
	server := httpserver.New(cfg.HTTPServerConfig(), router)

	go func() {
		<-ctx.Done()
		shutdownCtx, cancel := context.WithTimeout(context.Background(), cfg.ShutdownTimeout)
		defer cancel()
		if err := server.Shutdown(shutdownCtx); err != nil {
			log.Printf("payment-service shutdown failed: %v", err)
		}
		if err := loggingClient.Close(shutdownCtx); err != nil {
			log.Printf("payment-service log drain failed: %v", err)
		}
	}()

	log.Printf("payment-service listening on %s", cfg.Addr)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatal(err)
	}
}
