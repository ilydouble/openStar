package paymentlog

import (
	"context"
	"errors"
	"strings"

	"icore-payment-service/internal/domain/payment"
)

const (
	// OperationNativePrepay identifies a Native prepay workflow log event.
	OperationNativePrepay = "native_prepay"
	// OperationCloseOrder identifies a provider close-order workflow log event.
	OperationCloseOrder = "close_order"
	// OperationNativeNotification identifies a Native payment notification workflow log event.
	OperationNativeNotification = "native_notification"
)

// Logger is the application logging surface used by payment-service use cases.
type Logger interface {
	Info(context.Context, string, string, map[string]any) error
	Warning(context.Context, string, string, map[string]any) error
	Error(context.Context, string, string, map[string]any) error
}

// OrderMetadata contains non-secret local order fields for log metadata.
type OrderMetadata struct {
	OrderNo       string         `json:"order_no,omitempty"`
	PlanCode      string         `json:"plan_code,omitempty"`
	BillingPeriod string         `json:"billing_period,omitempty"`
	AmountCents   int64          `json:"amount_cents,omitempty"`
	Currency      string         `json:"currency,omitempty"`
	Status        payment.Status `json:"status,omitempty"`
}

// ProviderMetadata wraps provider-specific details under a stable abstraction layer.
type ProviderMetadata struct {
	Name           string                 `json:"name,omitempty"`
	MerchantID     string                 `json:"merchant_id,omitempty"`
	API            string                 `json:"api,omitempty"`
	RequestID      string                 `json:"request_id,omitempty"`
	ResponseSerial string                 `json:"response_serial,omitempty"`
	Error          *ProviderErrorMetadata `json:"error,omitempty"`
}

// ProviderErrorMetadata contains safe provider error details.
type ProviderErrorMetadata struct {
	HTTPStatus int    `json:"http_status,omitempty"`
	Code       string `json:"code,omitempty"`
	Message    string `json:"message,omitempty"`
}

// RequestMetadata contains trusted request correlation fields.
type RequestMetadata struct {
	ClientRequestID string `json:"client_request_id,omitempty"`
	UserPublicID    string `json:"user_public_id,omitempty"`
	PayerClientIP   string `json:"payer_client_ip,omitempty"`
}

// Metadata builds the common payment log metadata envelope.
func Metadata(operation string, order OrderMetadata, provider ProviderMetadata, request RequestMetadata) map[string]any {
	return map[string]any{
		"domain":    "payment",
		"operation": strings.TrimSpace(operation),
		"order":     order,
		"provider":  provider,
		"request":   request,
	}
}

// ProviderMetadataFromError extracts provider-neutral log fields from an error.
func ProviderMetadataFromError(providerName string, merchantID string, api string, err error) ProviderMetadata {
	metadata := ProviderMetadata{
		Name:       strings.TrimSpace(providerName),
		MerchantID: strings.TrimSpace(merchantID),
		API:        strings.TrimSpace(api),
	}
	if err == nil {
		return metadata
	}
	var providerErr *payment.ProviderError
	if errors.As(err, &providerErr) {
		if providerErr.Provider != "" {
			metadata.Name = providerErr.Provider
		}
		if providerErr.API != "" {
			metadata.API = providerErr.API
		}
		metadata.RequestID = providerErr.RequestID
		metadata.ResponseSerial = providerErr.ResponseSerial
		metadata.Error = &ProviderErrorMetadata{
			HTTPStatus: providerErr.HTTPStatus,
			Code:       providerErr.Code,
			Message:    safeErrorMessage(providerErr.Message),
		}
		return metadata
	}
	metadata.Error = &ProviderErrorMetadata{Message: safeErrorMessage(err.Error())}
	return metadata
}

// OrderMetadataFromOrder extracts non-secret order fields from a payment order.
func OrderMetadataFromOrder(order payment.Order) OrderMetadata {
	return OrderMetadata{
		OrderNo:       order.OrderNo,
		PlanCode:      order.PlanCode,
		BillingPeriod: order.BillingPeriod,
		AmountCents:   order.AmountCents,
		Currency:      order.Currency,
		Status:        order.Status,
	}
}

// safeErrorMessage returns a bounded provider error message for log metadata.
func safeErrorMessage(message string) string {
	message = strings.TrimSpace(strings.ReplaceAll(message, "\n", " "))
	if message == "" {
		return ""
	}
	if containsSensitiveMarker(message) {
		return "provider request failed"
	}
	if len(message) > 512 {
		return message[:512]
	}
	return message
}

// containsSensitiveMarker reports whether an error message appears to include credentials or signed headers.
func containsSensitiveMarker(message string) bool {
	lower := strings.ToLower(message)
	for _, marker := range []string{
		"authorization",
		"wechatpay-signature",
		"api_v3_key",
		"apiv3",
		"private key",
	} {
		if strings.Contains(lower, marker) {
			return true
		}
	}
	return false
}
