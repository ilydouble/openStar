package httpapi

import sharedhttp "xiehe-services-lib-go/httpapi"

func NewRouter(handler *Handler) *sharedhttp.Router {
	router := sharedhttp.NewRouter()
	auth := sharedhttp.TokenAuth(sharedhttp.TokenAuthConfig{
		Header:  storageServiceTokenHeader,
		Token:   handler.serviceToken,
		Message: "unauthorized",
	})

	router.GET("/health", handler.HandleHealth)
	router.POST("/buckets/ensure", auth, handler.HandleEnsureBucket)
	router.POST("/multipart/create", auth, handler.HandleCreateMultipart)
	router.POST("/multipart/complete", auth, handler.HandleCompleteMultipart)
	router.POST("/multipart/abort", auth, handler.HandleAbortMultipart)
	router.POST("/presign/get", auth, handler.HandlePresignGet)
	router.POST("/objects/stat", auth, handler.HandleStatObject)
	router.POST("/objects/delete", auth, handler.HandleDeleteObject)
	router.GET("/objects/*object_path", auth, handler.HandleGetObject)
	router.PUT("/objects/*object_path", auth, handler.HandlePutObject)
	return router
}
