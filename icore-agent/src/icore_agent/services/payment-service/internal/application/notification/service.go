package notification

import (
	"context"
	"errors"
	"net/http"
	"strings"

	"icore-payment-service/internal/application/paymentlog"
	"icore-payment-service/internal/domain/payment"
)

// Provider parses and verifies provider callback requests.
type Provider interface {
	ParseNotification(context.Context, *http.Request) (payment.ProviderNotification, error)
}

// Repository persists verified provider notification effects.
type Repository interface {
	MarkPaidByProvider(context.Context, payment.ProviderNotification) (payment.Order, error)
}

// ServiceConfig wires notification service dependencies.
type ServiceConfig struct {
	AppID      string
	MchID      string
	Provider   Provider
	Repository Repository
	Logger     paymentlog.Logger
}

// Service owns verified provider callback handling.
type Service struct {
	appID      string
	mchID      string
	provider   Provider
	repository Repository
	logger     paymentlog.Logger
}

var (
	// ErrNotificationMismatch indicates a verified notification is not for this merchant configuration.
	ErrNotificationMismatch = errors.New("wechatpay notification merchant mismatch")
	// ErrNotificationNotSuccess indicates a verified notification is not a success transaction.
	ErrNotificationNotSuccess = errors.New("wechatpay notification is not a success transaction")
)

// NewService creates a notification application service.
func NewService(config ServiceConfig) *Service {
	return &Service{
		appID:      strings.TrimSpace(config.AppID),
		mchID:      strings.TrimSpace(config.MchID),
		provider:   config.Provider,
		repository: config.Repository,
		logger:     config.Logger,
	}
}

// HandleWechatPayNative verifies and applies a WeChat Pay Native success callback.
func (service *Service) HandleWechatPayNative(ctx context.Context, request *http.Request) error {
	notification, err := service.provider.ParseNotification(ctx, request)
	if err != nil {
		service.logProviderWarning(ctx, "payment provider notification parse failed", requestIDFromRequest(request), payment.ProviderNotification{}, err)
		return err
	}
	transaction := notification.Transaction
	if transaction.AppID != service.appID || transaction.MchID != service.mchID {
		service.logProviderWarning(ctx, "payment provider notification merchant mismatch", requestIDFromRequest(request), notification, ErrNotificationMismatch)
		return ErrNotificationMismatch
	}
	if transaction.ProviderTradeState != "SUCCESS" {
		service.logProviderWarning(ctx, "payment provider notification ignored", requestIDFromRequest(request), notification, ErrNotificationNotSuccess)
		return ErrNotificationNotSuccess
	}
	if _, err = service.repository.MarkPaidByProvider(ctx, notification); err != nil {
		service.logProviderError(ctx, "payment provider notification apply failed", requestIDFromRequest(request), notification, err)
		return err
	}
	service.logProviderInfo(ctx, "payment provider notification applied", requestIDFromRequest(request), notification)
	return nil
}

// logProviderWarning records a recoverable provider notification failure.
func (service *Service) logProviderWarning(ctx context.Context, message string, traceID string, notification payment.ProviderNotification, err error) {
	if service.logger == nil {
		return
	}
	_ = service.logger.Warning(ctx, message, traceID, service.notificationMetadata(notification, err))
}

// logProviderError records a failed provider notification state transition.
func (service *Service) logProviderError(ctx context.Context, message string, traceID string, notification payment.ProviderNotification, err error) {
	if service.logger == nil {
		return
	}
	_ = service.logger.Error(ctx, message, traceID, service.notificationMetadata(notification, err))
}

// logProviderInfo records a successful provider notification state transition.
func (service *Service) logProviderInfo(ctx context.Context, message string, traceID string, notification payment.ProviderNotification) {
	if service.logger == nil {
		return
	}
	_ = service.logger.Info(ctx, message, traceID, service.notificationMetadata(notification, nil))
}

// notificationMetadata builds the common metadata envelope for provider notification logs.
func (service *Service) notificationMetadata(notification payment.ProviderNotification, err error) map[string]any {
	transaction := notification.Transaction
	return paymentlog.Metadata(
		paymentlog.OperationNativeNotification,
		paymentlog.OrderMetadata{
			OrderNo:     transaction.MerchantOrderNo,
			AmountCents: transaction.AmountCents,
			Currency:    transaction.Currency,
		},
		paymentlog.ProviderMetadataFromError(payment.ProviderWeChatPay, service.mchID, "native.notification", err),
		paymentlog.RequestMetadata{},
	)
}

// requestIDFromRequest extracts gateway correlation id from an HTTP request.
func requestIDFromRequest(request *http.Request) string {
	if request == nil {
		return ""
	}
	return strings.TrimSpace(request.Header.Get("X-Request-ID"))
}
