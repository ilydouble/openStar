package httpv1

import (
	"net/http"

	"github.com/go-chi/chi/v5"
)

// NewRouter creates the Chi router for payment-service HTTP v1 APIs.
func NewRouter(config HandlerConfig) *chi.Mux {
	handler := newHandler(config)
	router := chi.NewRouter()
	router.Get("/health", handler.health)
	router.Get("/ready", handler.ready)
	router.Post("/api/v1/payment/native/prepay", handler.createNativePrepay)
	router.Get("/api/v1/payment/orders/{out_trade_no}", func(w http.ResponseWriter, r *http.Request) {
		handler.getOrder(w, r, chi.URLParam(r, "out_trade_no"))
	})
	router.Post("/api/v1/payment/orders/{out_trade_no}/close", func(w http.ResponseWriter, r *http.Request) {
		handler.closeOrder(w, r, chi.URLParam(r, "out_trade_no"))
	})
	router.Post("/webhooks/wechatpay/native", handler.wechatPayNativeWebhook)
	return router
}
