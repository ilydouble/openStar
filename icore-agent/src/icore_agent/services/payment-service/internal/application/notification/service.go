package notification

import (
	"context"
	"errors"
	"net/http"
	"strings"

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
}

// Service owns verified provider callback handling.
type Service struct {
	appID      string
	mchID      string
	provider   Provider
	repository Repository
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
	}
}

// HandleWechatPayNative verifies and applies a WeChat Pay Native success callback.
func (service *Service) HandleWechatPayNative(ctx context.Context, request *http.Request) error {
	notification, err := service.provider.ParseNotification(ctx, request)
	if err != nil {
		return err
	}
	transaction := notification.Transaction
	if transaction.AppID != service.appID || transaction.MchID != service.mchID {
		return ErrNotificationMismatch
	}
	if transaction.TradeState != "SUCCESS" {
		return ErrNotificationNotSuccess
	}
	_, err = service.repository.MarkPaidByProvider(ctx, notification)
	return err
}
