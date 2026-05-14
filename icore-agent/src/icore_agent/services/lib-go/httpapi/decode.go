package httpapi

import (
	"encoding/json"
	"errors"
	"net/http"

	"github.com/gin-gonic/gin"
)

// DefaultJSONBodyLimit is the shared default max JSON body size for service APIs.
const DefaultJSONBodyLimit int64 = 1 << 20

// DecodeJSON reads a bounded JSON request body into target.
func DecodeJSON(ctx *gin.Context, target any, maxBytes int64) bool {
	if maxBytes <= 0 {
		maxBytes = DefaultJSONBodyLimit
	}

	body := http.MaxBytesReader(ctx.Writer, ctx.Request.Body, maxBytes)
	defer body.Close()

	decoder := json.NewDecoder(body)
	if err := decoder.Decode(target); err != nil {
		var maxBytesError *http.MaxBytesError
		if errors.As(err, &maxBytesError) {
			WriteError(ctx, http.StatusRequestEntityTooLarge, "request body too large")
			return false
		}
		WriteError(ctx, http.StatusBadRequest, err.Error())
		return false
	}
	return true
}
