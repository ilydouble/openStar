package httpv1

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"strings"

	"icore-payment-service/internal/application/checkout"
	"icore-payment-service/internal/domain/payment"

	sharedhttp "icore-services-lib-go/http/api"
	sharedheaders "icore-services-lib-go/http/headers"
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
	if err := sharedhttp.DecodeJSONStrict(w, r, &body, sharedhttp.DefaultJSONBodyLimit); err != nil {
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

func (handler *handler) getOrder(w http.ResponseWriter, r *http.Request, orderNo string) {
	userID := trustedUserID(r)
	if userID == "" {
		writeError(w, http.StatusUnauthorized, "missing_user_id", "missing trusted user id")
		return
	}
	result, err := handler.checkout.GetOrder(r.Context(), checkout.GetOrderInput{
		UserID:  userID,
		OrderNo: orderNo,
	})
	if err != nil {
		writeApplicationError(w, err)
		return
	}
	writeSuccess(w, http.StatusOK, result)
}

func (handler *handler) closeOrder(w http.ResponseWriter, r *http.Request, orderNo string) {
	userID := trustedUserID(r)
	if userID == "" {
		writeError(w, http.StatusUnauthorized, "missing_user_id", "missing trusted user id")
		return
	}
	result, err := handler.checkout.CloseOrder(r.Context(), checkout.CloseOrderInput{
		UserID:    userID,
		OrderNo:   orderNo,
		RequestID: requestIDFromGatewayHeaders(r),
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

func trustedUserID(r *http.Request) string {
	return strings.TrimSpace(r.Header.Get(sharedheaders.HeaderXUserID))
}

// requestIDFromGatewayHeaders extracts the gateway request correlation id.
func requestIDFromGatewayHeaders(r *http.Request) string {
	return strings.TrimSpace(r.Header.Get(sharedheaders.HeaderXRequestID))
}

func clientIPFromGatewayHeaders(r *http.Request) string {
	return sharedheaders.ClientIP(r)
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
