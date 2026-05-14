package httpapi

import sharedhttp "xiehe-services-lib-go/httpapi"

// NewRouter wires health and authenticated v1 ingestion routes.
func NewRouter(handler *Handler) *sharedhttp.Router {
	router := sharedhttp.NewRouter()
	auth := sharedhttp.TokenAuth(sharedhttp.TokenAuthConfig{
		Header:          serviceTokenHeader,
		Token:           handler.serviceToken,
		Message:         "invalid logging service token",
		AllowEmptyToken: true,
	})

	router.GET("/health", handler.HandleHealth)
	router.POST("/v1/log-events", auth, handler.HandleLogEvent)
	router.POST("/v1/log-events/batch", auth, handler.HandleLogEventBatch)
	return router
}
