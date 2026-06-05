package httpv1

import (
	"context"
	"encoding/json"
	"errors"
	"net"
	"net/http"
	"strings"

	"icore-payment-service/internal/application/checkout"
	"icore-payment-service/internal/domain/payment"
)

// CheckoutService is the application checkout surface used by HTTP handlers.
type CheckoutService interface {
	CreateNativePrepay(context.Context, checkout.CreateNativePrepayInput) (checkout.NativePrepayResult, error)
	GetOrder(context.Context, checkout.GetOrderInput) (checkout.OrderResult, error)
	CloseOrder(context.Context, checkout.CloseOrderInput) (checkout.OrderResult, error)
}

// NotificationService is the provider callback surface used by HTTP handlers.
type NotificationService interface {
	HandleWechatPayNative(context.Context, *http.Request) error
}

// HandlerConfig wires HTTP handlers to application services.
type HandlerConfig struct {
	Checkout     CheckoutService
	Notification NotificationService
	ReadyCheck   func(context.Context) error
}

type handler struct {
	checkout     CheckoutService
	notification NotificationService
	readyCheck   func(context.Context) error
}

type nativePrepayRequest struct {
	PlanCode        string `json:"plan_code"`
	BillingPeriod   string `json:"billing_period"`
	ClientRequestID string `json:"client_request_id"`
	PayerClientIP   string `json:"payer_client_ip"`
	UserID          string `json:"user_id"`
}

// newHandler creates the versioned HTTP handler set.
func newHandler(config HandlerConfig) *handler {
	return &handler{
		checkout:     config.Checkout,
		notification: config.Notification,
		readyCheck:   config.ReadyCheck,
	}
}

func (handler *handler) health(w http.ResponseWriter, _ *http.Request) {
	writeSuccess(w, http.StatusOK, map[string]string{"status": "ok", "service": "payment-service"})
}

func (handler *handler) ready(w http.ResponseWriter, r *http.Request) {
	if handler.readyCheck != nil {
		if err := handler.readyCheck(r.Context()); err != nil {
			writeError(w, http.StatusServiceUnavailable, "not_ready", "payment-service is not ready")
			return
		}
	}
	writeSuccess(w, http.StatusOK, map[string]string{"status": "ready", "service": "payment-service"})
}

func (handler *handler) createNativePrepay(w http.ResponseWriter, r *http.Request) {
	if handler.checkout == nil {
		writeError(w, http.StatusServiceUnavailable, "checkout_unavailable", "checkout service unavailable")
		return
	}
	userID := trustedUserID(r)
	if userID == "" {
		writeError(w, http.StatusUnauthorized, "missing_user_id", "missing trusted user id")
		return
	}
	var body nativePrepayRequest
	if err := decodeJSON(w, r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_request", "invalid payment request")
		return
	}
	payerClientIP := clientIPFromGatewayHeaders(r)
	if payerClientIP == "" {
		payerClientIP = body.PayerClientIP
	}
	result, err := handler.checkout.CreateNativePrepay(r.Context(), checkout.CreateNativePrepayInput{
		UserID:          userID,
		PlanCode:        body.PlanCode,
		BillingPeriod:   body.BillingPeriod,
		ClientRequestID: body.ClientRequestID,
		RequestID:       requestIDFromGatewayHeaders(r),
		PayerClientIP:   payerClientIP,
	})
	if err != nil {
		writeApplicationError(w, err)
		return
	}
	writeSuccess(w, http.StatusCreated, result)
}

func (handler *handler) getOrder(w http.ResponseWriter, r *http.Request, outTradeNo string) {
	userID := trustedUserID(r)
	if userID == "" {
		writeError(w, http.StatusUnauthorized, "missing_user_id", "missing trusted user id")
		return
	}
	result, err := handler.checkout.GetOrder(r.Context(), checkout.GetOrderInput{
		UserID:     userID,
		OutTradeNo: outTradeNo,
	})
	if err != nil {
		writeApplicationError(w, err)
		return
	}
	writeSuccess(w, http.StatusOK, result)
}

func (handler *handler) closeOrder(w http.ResponseWriter, r *http.Request, outTradeNo string) {
	userID := trustedUserID(r)
	if userID == "" {
		writeError(w, http.StatusUnauthorized, "missing_user_id", "missing trusted user id")
		return
	}
	result, err := handler.checkout.CloseOrder(r.Context(), checkout.CloseOrderInput{
		UserID:     userID,
		OutTradeNo: outTradeNo,
		RequestID:  requestIDFromGatewayHeaders(r),
	})
	if err != nil {
		writeApplicationError(w, err)
		return
	}
	writeSuccess(w, http.StatusOK, result)
}

func (handler *handler) wechatPayNativeWebhook(w http.ResponseWriter, r *http.Request) {
	if handler.notification == nil {
		writeWechatWebhookFailure(w, http.StatusServiceUnavailable, "notification service unavailable")
		return
	}
	if err := handler.notification.HandleWechatPayNative(r.Context(), r); err != nil {
		writeWechatWebhookFailure(w, http.StatusBadRequest, "invalid notification")
		return
	}
	writeWechatWebhookSuccess(w)
}

func decodeJSON(w http.ResponseWriter, r *http.Request, target any) error {
	r.Body = http.MaxBytesReader(w, r.Body, 1<<20)
	decoder := json.NewDecoder(r.Body)
	decoder.DisallowUnknownFields()
	return decoder.Decode(target)
}

func trustedUserID(r *http.Request) string {
	return strings.TrimSpace(r.Header.Get("X-User-ID"))
}

// requestIDFromGatewayHeaders extracts the gateway request correlation id.
func requestIDFromGatewayHeaders(r *http.Request) string {
	return strings.TrimSpace(r.Header.Get("X-Request-ID"))
}

func clientIPFromGatewayHeaders(r *http.Request) string {
	if forwardedFor := strings.TrimSpace(r.Header.Get("X-Forwarded-For")); forwardedFor != "" {
		parts := strings.Split(forwardedFor, ",")
		if len(parts) > 0 {
			return strings.TrimSpace(parts[0])
		}
	}
	if realIP := strings.TrimSpace(r.Header.Get("X-Real-IP")); realIP != "" {
		return realIP
	}
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err == nil {
		return host
	}
	return strings.TrimSpace(r.RemoteAddr)
}

func writeApplicationError(w http.ResponseWriter, err error) {
	switch {
	case errors.Is(err, checkout.ErrInvalidRequest):
		writeError(w, http.StatusBadRequest, "invalid_request", "invalid payment request")
	case errors.Is(err, checkout.ErrCatalogItemUnavailable):
		writeError(w, http.StatusBadRequest, "catalog_item_unavailable", "payment catalog item unavailable")
	case errors.Is(err, payment.ErrOrderNotFound):
		writeError(w, http.StatusNotFound, "order_not_found", "payment order not found")
	case errors.Is(err, payment.ErrIdempotencyConflict):
		writeError(w, http.StatusConflict, "idempotency_conflict", "payment idempotency conflict")
	case errors.Is(err, payment.ErrInvalidOrderState):
		writeError(w, http.StatusConflict, "invalid_order_state", "invalid payment order state")
	default:
		writeError(w, http.StatusBadGateway, "payment_provider_error", "payment provider error")
	}
}

func writeWechatWebhookSuccess(w http.ResponseWriter) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(map[string]string{"code": "SUCCESS", "message": "成功"})
}

func writeWechatWebhookFailure(w http.ResponseWriter, status int, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(map[string]string{"code": "FAIL", "message": message})
}
