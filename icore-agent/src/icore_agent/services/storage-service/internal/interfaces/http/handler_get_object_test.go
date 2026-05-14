package httpapi

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	appstorage "xiehe-storage-service/internal/application/storage"
	domain "xiehe-storage-service/internal/domain/storage"
)

type fakeObjectRepository struct {
	body []byte
}

func (repo fakeObjectRepository) EnsureBucket(context.Context, string) error { return nil }
func (repo fakeObjectRepository) CreateMultipartUpload(context.Context, domain.CreateMultipartRequest) (domain.MultipartUpload, error) {
	return domain.MultipartUpload{}, nil
}
func (repo fakeObjectRepository) CompleteMultipartUpload(context.Context, domain.CompleteMultipartRequest) (domain.CompleteMultipartResult, error) {
	return domain.CompleteMultipartResult{}, nil
}
func (repo fakeObjectRepository) AbortMultipartUpload(context.Context, domain.AbortMultipartRequest) error {
	return nil
}
func (repo fakeObjectRepository) PresignGetObject(context.Context, domain.ObjectRef, int) (string, error) {
	return "", nil
}
func (repo fakeObjectRepository) StatObject(context.Context, domain.ObjectRef) (domain.ObjectStat, error) {
	return domain.ObjectStat{}, nil
}
func (repo fakeObjectRepository) DeleteObject(context.Context, domain.ObjectRef) error { return nil }
func (repo fakeObjectRepository) PutObject(context.Context, appstorage.PutObjectInput) (domain.PutObjectResult, error) {
	return domain.PutObjectResult{}, nil
}
func (repo fakeObjectRepository) GetObject(ctx context.Context, ref domain.ObjectRef) (domain.ObjectStream, error) {
	return domain.ObjectStream{
		Bucket:      ref.Bucket,
		ObjectKey:   ref.ObjectKey,
		Body:        io.NopCloser(strings.NewReader(string(repo.body))),
		Size:        int64(len(repo.body)),
		ETag:        "etag-object",
		ContentType: "image/png",
	}, nil
}

func TestHandleGetObjectStreamsAuthenticatedObject(t *testing.T) {
	service := appstorage.NewService(fakeObjectRepository{body: []byte("image-bytes")})
	router := NewRouter(NewHandler(service, "secret-token"))

	request := httptest.NewRequest(http.MethodGet, "/objects/medical-image-files/path/to/image.png", nil)
	request.Header.Set(storageServiceTokenHeader, "secret-token")
	response := httptest.NewRecorder()

	router.ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", response.Code, response.Body.String())
	}
	if response.Body.String() != "image-bytes" {
		t.Fatalf("unexpected body %q", response.Body.String())
	}
	if response.Header().Get("Content-Type") != "image/png" {
		t.Fatalf("unexpected content type %q", response.Header().Get("Content-Type"))
	}
	if response.Header().Get("ETag") != `"etag-object"` {
		t.Fatalf("unexpected etag %q", response.Header().Get("ETag"))
	}
}

func TestHandleGetObjectRequiresStorageToken(t *testing.T) {
	service := appstorage.NewService(fakeObjectRepository{body: []byte("image-bytes")})
	router := NewRouter(NewHandler(service, "secret-token"))

	request := httptest.NewRequest(http.MethodGet, "/objects/medical-image-files/path/to/image.png", nil)
	response := httptest.NewRecorder()

	router.ServeHTTP(response, request)

	if response.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d", response.Code)
	}
}

func TestHandlePutObjectRejectsBodiesOverLimit(t *testing.T) {
	service := appstorage.NewService(fakeObjectRepository{body: []byte("image-bytes")})
	router := NewRouter(NewHandler(service, "secret-token", WithMaxUploadBodyBytes(4)))

	request := httptest.NewRequest(
		http.MethodPut,
		"/objects/medical-image-files/path/to/image.png",
		strings.NewReader("image-bytes"),
	)
	request.Header.Set(storageServiceTokenHeader, "secret-token")
	response := httptest.NewRecorder()

	router.ServeHTTP(response, request)

	if response.Code != http.StatusRequestEntityTooLarge {
		t.Fatalf("expected 413, got %d: %s", response.Code, response.Body.String())
	}
}
