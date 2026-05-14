package httpapi

import (
	"errors"
	"io"
	"net/http"
	"os"
	"strconv"
	"strings"

	sharedhttp "xiehe-services-lib-go/httpapi"
	appstorage "xiehe-storage-service/internal/application/storage"
	domain "xiehe-storage-service/internal/domain/storage"
)

type Handler struct {
	storageService     *appstorage.Service
	serviceToken       string
	maxUploadBodyBytes int64
}

const defaultMaxUploadBodyBytes int64 = 512 << 20

type HandlerOption func(*Handler)

// WithMaxUploadBodyBytes sets the maximum accepted PUT object body size.
func WithMaxUploadBodyBytes(limit int64) HandlerOption {
	return func(handler *Handler) {
		if limit > 0 {
			handler.maxUploadBodyBytes = limit
		}
	}
}

// NewHandler binds the storage application service, service token, and HTTP limits.
func NewHandler(storageService *appstorage.Service, serviceToken string, options ...HandlerOption) *Handler {
	handler := &Handler{
		storageService:     storageService,
		serviceToken:       serviceToken,
		maxUploadBodyBytes: defaultMaxUploadBodyBytes,
	}
	for _, option := range options {
		option(handler)
	}
	return handler
}

func (handler *Handler) HandleHealth(ctx *sharedhttp.Context) {
	sharedhttp.WriteJSON(ctx, http.StatusOK, map[string]string{"status": "ok"})
}

func (handler *Handler) HandleEnsureBucket(ctx *sharedhttp.Context) {
	var request ensureBucketRequest
	if !sharedhttp.DecodeJSON(ctx, &request, sharedhttp.DefaultJSONBodyLimit) {
		return
	}

	err := handler.storageService.EnsureBucket(ctx.Request.Context(), request.Bucket)
	if err != nil {
		writeServiceError(ctx, err)
		return
	}

	sharedhttp.WriteJSON(ctx, http.StatusOK, map[string]string{"bucket": request.Bucket})
}

func (handler *Handler) HandleCreateMultipart(ctx *sharedhttp.Context) {
	var request createMultipartRequest
	if !sharedhttp.DecodeJSON(ctx, &request, sharedhttp.DefaultJSONBodyLimit) {
		return
	}

	upload, err := handler.storageService.CreateMultipartUpload(
		ctx.Request.Context(),
		toCreateMultipartDomain(request),
	)
	if err != nil {
		writeServiceError(ctx, err)
		return
	}

	sharedhttp.WriteJSON(ctx, http.StatusOK, map[string]any{
		"bucket":     upload.Bucket,
		"object_key": upload.ObjectKey,
		"upload_id":  upload.UploadID,
		"parts":      toPartURLs(upload.Parts),
	})
}

func (handler *Handler) HandleCompleteMultipart(ctx *sharedhttp.Context) {
	var request completeMultipartRequest
	if !sharedhttp.DecodeJSON(ctx, &request, sharedhttp.DefaultJSONBodyLimit) {
		return
	}

	result, err := handler.storageService.CompleteMultipartUpload(
		ctx.Request.Context(),
		toCompleteMultipartDomain(request),
	)
	if err != nil {
		writeServiceError(ctx, err)
		return
	}

	sharedhttp.WriteJSON(ctx, http.StatusOK, map[string]any{
		"bucket":     result.Bucket,
		"object_key": result.ObjectKey,
		"etag":       result.ETag,
	})
}

func (handler *Handler) HandleAbortMultipart(ctx *sharedhttp.Context) {
	var request completeMultipartRequest
	if !sharedhttp.DecodeJSON(ctx, &request, sharedhttp.DefaultJSONBodyLimit) {
		return
	}

	err := handler.storageService.AbortMultipartUpload(ctx.Request.Context(), toAbortMultipartDomain(request))
	if err != nil {
		writeServiceError(ctx, err)
		return
	}

	sharedhttp.WriteJSON(ctx, http.StatusOK, map[string]string{"status": "aborted"})
}

func (handler *Handler) HandlePresignGet(ctx *sharedhttp.Context) {
	var request objectRequest
	if !sharedhttp.DecodeJSON(ctx, &request, sharedhttp.DefaultJSONBodyLimit) {
		return
	}

	url, err := handler.storageService.PresignGetObject(
		ctx.Request.Context(),
		domain.ObjectRef{Bucket: request.Bucket, ObjectKey: request.ObjectKey},
		request.ExpiresIn,
	)
	if err != nil {
		writeServiceError(ctx, err)
		return
	}

	sharedhttp.WriteJSON(ctx, http.StatusOK, map[string]string{"url": url})
}

func (handler *Handler) HandleStatObject(ctx *sharedhttp.Context) {
	var request objectRequest
	if !sharedhttp.DecodeJSON(ctx, &request, sharedhttp.DefaultJSONBodyLimit) {
		return
	}

	stat, err := handler.storageService.StatObject(
		ctx.Request.Context(),
		domain.ObjectRef{Bucket: request.Bucket, ObjectKey: request.ObjectKey},
	)
	if err != nil {
		writeServiceError(ctx, err)
		return
	}

	sharedhttp.WriteJSON(ctx, http.StatusOK, map[string]any{
		"bucket":       stat.Bucket,
		"object_key":   stat.ObjectKey,
		"size":         stat.Size,
		"etag":         stat.ETag,
		"content_type": stat.ContentType,
		"metadata":     stat.Metadata,
	})
}

func (handler *Handler) HandleDeleteObject(ctx *sharedhttp.Context) {
	var request objectRequest
	if !sharedhttp.DecodeJSON(ctx, &request, sharedhttp.DefaultJSONBodyLimit) {
		return
	}

	err := handler.storageService.DeleteObject(
		ctx.Request.Context(),
		domain.ObjectRef{Bucket: request.Bucket, ObjectKey: request.ObjectKey},
	)
	if err != nil {
		writeServiceError(ctx, err)
		return
	}

	sharedhttp.WriteJSON(ctx, http.StatusOK, map[string]string{"status": "deleted"})
}

func (handler *Handler) HandleGetObject(ctx *sharedhttp.Context) {
	bucket, objectKey, ok := parseObjectPath(ctx.Request.URL.Path)
	if !ok {
		sharedhttp.WriteError(ctx, http.StatusBadRequest, "path must be /objects/{bucket}/{object_key}")
		return
	}

	stream, err := handler.storageService.GetObject(
		ctx.Request.Context(),
		domain.ObjectRef{Bucket: bucket, ObjectKey: objectKey},
	)
	if err != nil {
		writeServiceError(ctx, err)
		return
	}
	defer stream.Body.Close()

	if stream.ContentType != "" {
		ctx.Writer.Header().Set("Content-Type", stream.ContentType)
	}
	if stream.Size >= 0 {
		ctx.Writer.Header().Set("Content-Length", strconv.FormatInt(stream.Size, 10))
	}
	if stream.ETag != "" {
		ctx.Writer.Header().Set("ETag", `"`+strings.Trim(stream.ETag, `"`)+`"`)
	}
	ctx.Writer.WriteHeader(http.StatusOK)
	if _, err := io.Copy(ctx.Writer, stream.Body); err != nil {
		return
	}
}

func (handler *Handler) HandlePutObject(ctx *sharedhttp.Context) {
	bucket, objectKey, ok := parseObjectPath(ctx.Request.URL.Path)
	if !ok {
		sharedhttp.WriteError(ctx, http.StatusBadRequest, "path must be /objects/{bucket}/{object_key}")
		return
	}

	body, contentLength, err := seekableBody(http.MaxBytesReader(ctx.Writer, ctx.Request.Body, handler.maxUploadBodyBytes))
	if err != nil {
		var maxBytesError *http.MaxBytesError
		if errors.As(err, &maxBytesError) {
			sharedhttp.WriteError(ctx, http.StatusRequestEntityTooLarge, "upload body exceeds storage-service limit")
			return
		}
		sharedhttp.WriteError(ctx, http.StatusInternalServerError, err.Error())
		return
	}
	defer func() {
		name := body.Name()
		_ = body.Close()
		_ = os.Remove(name)
	}()

	result, err := handler.storageService.PutObject(
		ctx.Request.Context(),
		appstorage.PutObjectInput{
			Bucket:        bucket,
			ObjectKey:     objectKey,
			Body:          body,
			ContentLength: contentLength,
			ContentType:   ctx.Request.Header.Get("Content-Type"),
		},
	)
	if err != nil {
		writeServiceError(ctx, err)
		return
	}

	sharedhttp.WriteJSON(ctx, http.StatusOK, map[string]any{
		"bucket":     result.Bucket,
		"object_key": result.ObjectKey,
		"etag":       result.ETag,
	})
}

func parseObjectPath(path string) (string, string, bool) {
	trimmed := strings.TrimPrefix(path, "/objects/")
	parts := strings.SplitN(trimmed, "/", 2)
	if len(parts) != 2 || parts[0] == "" || parts[1] == "" {
		return "", "", false
	}
	return parts[0], parts[1], true
}

func writeServiceError(ctx *sharedhttp.Context, err error) {
	switch {
	case errors.Is(err, domain.ErrBucketRequired),
		errors.Is(err, domain.ErrObjectKeyRequired),
		errors.Is(err, domain.ErrInvalidPartCount),
		errors.Is(err, domain.ErrMultipartPartsRequired),
		errors.Is(err, domain.ErrUploadIDRequired):
		sharedhttp.WriteError(ctx, http.StatusBadRequest, err.Error())
	case errors.Is(err, domain.ErrObjectNotFound):
		sharedhttp.WriteError(ctx, http.StatusNotFound, err.Error())
	default:
		sharedhttp.WriteError(ctx, http.StatusBadGateway, err.Error())
	}
}
