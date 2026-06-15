package reconciliation

import (
	"context"
	"fmt"
	"time"

	"icore-payment-service/internal/domain/payment"
)

// Repository persists payment reconciliation state transitions.
type Repository interface {
	ClaimPendingReconciliationOrders(context.Context, int, time.Time) ([]payment.Order, error)
	MarkPaidByProvider(context.Context, payment.ProviderNotification) (payment.Order, error)
	MarkExpiredByProvider(context.Context, string, time.Time) (payment.Order, error)
	MarkClosedByProvider(context.Context, string, time.Time) (payment.Order, error)
}

// Provider queries and closes provider-side payment orders.
type Provider interface {
	QueryOrderByOutTradeNo(context.Context, string) (payment.ProviderTransaction, error)
	CloseOrder(context.Context, string) error
}

// Logger records reconciliation errors without stopping the worker.
type Logger interface {
	Printf(string, ...any)
}

// Config wires payment reconciliation dependencies and defaults.
type Config struct {
	Repository   Repository
	Provider     Provider
	Logger       Logger
	AppID        string
	MchID        string
	BatchSize    int
	PollInterval time.Duration
	QueryTimeout time.Duration
	Now          func() time.Time
}

// Service reconciles local pending payment orders against WeChat Pay.
type Service struct {
	repository   Repository
	provider     Provider
	logger       Logger
	appID        string
	mchID        string
	batchSize    int
	pollInterval time.Duration
	queryTimeout time.Duration
	now          func() time.Time
}

// NewService creates a reconciliation service.
func NewService(config Config) *Service {
	batchSize := config.BatchSize
	if batchSize <= 0 {
		batchSize = 50
	}
	pollInterval := config.PollInterval
	if pollInterval <= 0 {
		pollInterval = 30 * time.Second
	}
	queryTimeout := config.QueryTimeout
	if queryTimeout <= 0 {
		queryTimeout = 10 * time.Second
	}
	now := config.Now
	if now == nil {
		now = time.Now
	}
	return &Service{
		repository:   config.Repository,
		provider:     config.Provider,
		logger:       config.Logger,
		appID:        config.AppID,
		mchID:        config.MchID,
		batchSize:    batchSize,
		pollInterval: pollInterval,
		queryTimeout: queryTimeout,
		now:          now,
	}
}

// Run polls for pending payment orders until the context is canceled.
func (service *Service) Run(ctx context.Context) {
	ticker := time.NewTicker(service.pollInterval)
	defer ticker.Stop()
	for {
		if err := service.RunOnce(ctx); err != nil {
			service.logf("payment reconciliation failed: %v", err)
		}
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		}
	}
}

// RunOnce reconciles one batch of locally unpaid payment orders.
func (service *Service) RunOnce(ctx context.Context) error {
	if service.repository == nil || service.provider == nil {
		return fmt.Errorf("payment reconciliation dependencies are required")
	}
	now := service.now().UTC()
	orders, err := service.repository.ClaimPendingReconciliationOrders(ctx, service.batchSize, now)
	if err != nil {
		return err
	}
	for _, order := range orders {
		service.reconcileOrder(ctx, order, now)
	}
	return nil
}

func (service *Service) reconcileOrder(ctx context.Context, order payment.Order, now time.Time) {
	queryCtx, cancel := context.WithTimeout(ctx, service.queryTimeout)
	transaction, err := service.provider.QueryOrderByOutTradeNo(queryCtx, order.OrderNo)
	cancel()
	if err != nil {
		service.logf("payment reconciliation query failed order_no=%s: %v", order.OrderNo, err)
		return
	}

	switch transaction.ProviderTradeState {
	case "SUCCESS":
		if service.appID != "" && transaction.AppID != service.appID {
			service.logf("payment reconciliation app mismatch order_no=%s", order.OrderNo)
			return
		}
		if service.mchID != "" && transaction.MchID != service.mchID {
			service.logf("payment reconciliation merchant mismatch order_no=%s", order.OrderNo)
			return
		}
		if _, err := service.repository.MarkPaidByProvider(ctx, payment.ProviderNotification{
			EventID:     reconciliationEventID(transaction),
			EventType:   "payment.reconciliation.query",
			Transaction: transaction,
			RawPayload:  []byte(`{}`),
		}); err != nil {
			service.logf("payment reconciliation mark paid failed order_no=%s: %v", order.OrderNo, err)
		}
	case "CLOSED":
		if _, err := service.repository.MarkClosedByProvider(ctx, order.OrderNo, now); err != nil {
			service.logf("payment reconciliation mark closed failed order_no=%s: %v", order.OrderNo, err)
		}
	case "NOTPAY":
		if orderExpired(order, now) {
			if err := service.provider.CloseOrder(ctx, order.OrderNo); err != nil {
				service.logf("payment reconciliation close expired order failed order_no=%s: %v", order.OrderNo, err)
				return
			}
			if _, err := service.repository.MarkExpiredByProvider(ctx, order.OrderNo, now); err != nil {
				service.logf("payment reconciliation mark expired failed order_no=%s: %v", order.OrderNo, err)
			}
		}
	}
}

func orderExpired(order payment.Order, now time.Time) bool {
	if order.ProviderTransaction == nil || order.ProviderTransaction.ExpiresAt == nil {
		return false
	}
	return !order.ProviderTransaction.ExpiresAt.After(now)
}

func reconciliationEventID(transaction payment.ProviderTransaction) string {
	if transaction.ProviderTransactionID != "" {
		return "reconcile:" + transaction.MerchantOrderNo + ":" + transaction.ProviderTransactionID
	}
	return "reconcile:" + transaction.MerchantOrderNo
}

func (service *Service) logf(format string, args ...any) {
	if service.logger != nil {
		service.logger.Printf(format, args...)
	}
}
