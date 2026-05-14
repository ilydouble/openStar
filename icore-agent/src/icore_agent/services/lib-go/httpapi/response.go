package httpapi

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
)

// WriteJSON wraps successful payloads in the API envelope shared by Go services.
func WriteJSON(ctx *gin.Context, status int, payload any) {
	message := "操作成功"
	if status >= http.StatusBadRequest {
		message = "请求失败"
	}

	ctx.JSON(status, gin.H{
		"code":      status,
		"message":   message,
		"data":      payload,
		"timestamp": time.Now().UTC().Format(time.RFC3339Nano),
	})
}

// WriteError wraps API errors in the shared envelope and aborts the Gin handler chain.
func WriteError(ctx *gin.Context, status int, message string) {
	ctx.AbortWithStatusJSON(status, gin.H{
		"code":       status,
		"message":    message,
		"data":       nil,
		"error_code": http.StatusText(status),
		"timestamp":  time.Now().UTC().Format(time.RFC3339Nano),
	})
}
