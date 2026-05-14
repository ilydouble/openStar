package httpapi

import "github.com/gin-gonic/gin"

// Context is the Gin request context type used by service handlers.
type Context = gin.Context

// Router is the Gin engine type used by service entrypoints.
type Router = gin.Engine

// NewRouter returns a Gin router with recovery middleware and no request logger.
func NewRouter() *Router {
	router := gin.New()
	router.Use(gin.Recovery())
	return router
}
