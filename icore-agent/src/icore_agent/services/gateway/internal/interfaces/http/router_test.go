package httpapi

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	appgateway "icore-gateway/internal/application/gateway"
	domain "icore-gateway/internal/domain/gateway"
	jwtinfra "icore-gateway/internal/infrastructure/jwt"
	proxyinfra "icore-gateway/internal/infrastructure/proxy"
	sharedlogging "icore-services-lib-go/logging"
)

type captureAccessLogger struct {
	events []domain.AccessLogEvent
}

func (logger *captureAccessLogger) Emit(event domain.AccessLogEvent) {
	logger.events = append(logger.events, event)
}

type staticLimiter struct {
	decision domain.RateLimitDecision
}

func (limiter staticLimiter) Allow(_ context.Context, _ string) (domain.RateLimitDecision, error) {
	return limiter.decision, nil
}

type roundTripFunc func(*http.Request) (*http.Response, error)

func (fn roundTripFunc) RoundTrip(request *http.Request) (*http.Response, error) {
	return fn(request)
}

type routerTestConfig struct {
	backendURL string
	secret     string
	logger     *captureAccessLogger
	limiter    appgateway.RateLimiter
	transport  http.RoundTripper
	now        func() time.Time
	location   *time.Location
}

func TestGatewayInjectsGeneratedRequestIDAndLogsMetadata(t *testing.T) {
	upstreamRequestID := ""
	transport := roundTripFunc(func(request *http.Request) (*http.Response, error) {
		upstreamRequestID = request.Header.Get(domain.RequestIDHeader)
		return testResponse(http.StatusAccepted, `{"ok":true}`), nil
	})

	logger := &captureAccessLogger{}
	router := newTestRouter(routerTestConfig{
		logger:    logger,
		transport: transport,
		limiter: staticLimiter{decision: domain.RateLimitDecision{
			Allowed: true,
			Result:  "allowed",
		}},
		now: func() time.Time {
			return time.Date(2026, 5, 15, 8, 0, 0, 0, time.FixedZone("CST", 8*3600))
		},
	})

	response := httptest.NewRecorder()
	router.ServeHTTP(response, httptest.NewRequest(http.MethodPost, "/api/v1/account/login?source=web", nil))

	requestID := response.Header().Get(domain.RequestIDHeader)
	if response.Code != http.StatusAccepted {
		t.Fatalf("expected upstream status, got %d", response.Code)
	}
	if requestID == "" {
		t.Fatal("gateway should return a generated X-Request-ID")
	}
	if upstreamRequestID != requestID {
		t.Fatalf("upstream request id %q did not match response %q", upstreamRequestID, requestID)
	}
	if len(logger.events) != 1 {
		t.Fatalf("expected one gateway log event, got %d", len(logger.events))
	}

	event := logger.events[0]
	metadata := event.Metadata
	if event.Service != "icore-gateway" {
		t.Fatalf("unexpected service %q", event.Service)
	}
	if event.TraceID != requestID {
		t.Fatalf("unexpected trace id %q", event.TraceID)
	}
	if metadata.RequestTimestamp != "2026-05-15T08:00:00+08:00" {
		t.Fatalf("unexpected timestamp %q", metadata.RequestTimestamp)
	}
	if metadata.RequestID != requestID || metadata.Method != http.MethodPost {
		t.Fatalf("metadata did not capture request identity: %#v", metadata)
	}
	if metadata.Path != "/api/v1/account/login" || metadata.Query != "source=web" {
		t.Fatalf("metadata did not capture path/query: %#v", metadata)
	}
	if metadata.AuthResult != domain.AuthResultPublic {
		t.Fatalf("expected public auth result, got %q", metadata.AuthResult)
	}
	if metadata.UpstreamService == nil || *metadata.UpstreamService != "icore-agent" {
		t.Fatalf("expected icore-agent upstream, got %#v", metadata.UpstreamService)
	}
	if metadata.UpstreamStatusCode == nil || *metadata.UpstreamStatusCode != http.StatusAccepted {
		t.Fatalf("unexpected upstream status %#v", metadata.UpstreamStatusCode)
	}
	if metadata.FinalStatusCode != http.StatusAccepted {
		t.Fatalf("unexpected final status %d", metadata.FinalStatusCode)
	}
	if metadata.RateLimitResult != "allowed" {
		t.Fatalf("unexpected rate limit result %q", metadata.RateLimitResult)
	}
}

// TestGatewayFormatsTimestampsInConfiguredLocation keeps access logs out of implicit UTC.
func TestGatewayFormatsTimestampsInConfiguredLocation(t *testing.T) {
	location, err := time.LoadLocation("Asia/Shanghai")
	if err != nil {
		t.Fatalf("load test location: %v", err)
	}
	logger := &captureAccessLogger{}
	router := newTestRouter(routerTestConfig{
		logger:   logger,
		location: location,
		now: func() time.Time {
			return time.Date(2026, 5, 16, 7, 22, 52, 742470455, time.UTC)
		},
	})

	response := httptest.NewRecorder()
	router.ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/health", nil))

	if len(logger.events) != 1 {
		t.Fatalf("expected one gateway log event, got %d", len(logger.events))
	}
	metadata := logger.events[0].Metadata
	want := "2026-05-16T15:22:52.742470455+08:00"
	if got := metadata.RequestTimestamp; got != want {
		t.Fatalf("metadata timestamp = %q, want %q", got, want)
	}
	if got := logger.events[0].Timestamp.Format(time.RFC3339Nano); got != want {
		t.Fatalf("event timestamp = %q, want %q", got, want)
	}
}

func TestGatewayRejectsProtectedRouteWithoutJWT(t *testing.T) {
	upstreamHit := false
	transport := roundTripFunc(func(request *http.Request) (*http.Response, error) {
		upstreamHit = true
		return testResponse(http.StatusOK, ""), nil
	})

	logger := &captureAccessLogger{}
	router := newTestRouter(routerTestConfig{logger: logger, transport: transport, now: time.Now})

	response := httptest.NewRecorder()
	router.ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/api/v1/account/me", nil))

	if response.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d", response.Code)
	}
	if upstreamHit {
		t.Fatal("protected request should not reach upstream")
	}
	if len(logger.events) != 1 {
		t.Fatalf("expected one log event, got %d", len(logger.events))
	}
	if logger.events[0].Level != sharedlogging.LogLevelWarning {
		t.Fatalf("expected warning log, got %q", logger.events[0].Level)
	}
	metadata := logger.events[0].Metadata
	if metadata.AuthResult != domain.AuthResultMissingToken {
		t.Fatalf("unexpected auth result %q", metadata.AuthResult)
	}
	if metadata.RejectReason == nil || *metadata.RejectReason != "missing bearer token" {
		t.Fatalf("unexpected reject reason %#v", metadata.RejectReason)
	}
}

func TestGatewayForwardsValidJWTIdentityHeaders(t *testing.T) {
	var userID string
	var roles string
	transport := roundTripFunc(func(request *http.Request) (*http.Response, error) {
		userID = request.Header.Get("X-User-ID")
		roles = request.Header.Get("X-User-Roles")
		return testResponse(http.StatusOK, ""), nil
	})

	secret := "test-secret-with-at-least-32-bytes"
	token := signTestJWT(t, secret, "user-1", []string{"owner", "admin"}, time.Now().Add(time.Hour))
	router := newTestRouter(routerTestConfig{
		secret:    secret,
		logger:    &captureAccessLogger{},
		transport: transport,
		now:       time.Now,
	})

	request := httptest.NewRequest(http.MethodGet, "/api/v1/account/me", nil)
	request.Header.Set("Authorization", "Bearer "+token)
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", response.Code)
	}
	if userID != "user-1" {
		t.Fatalf("expected forwarded user id, got %q", userID)
	}
	if roles != "owner,admin" {
		t.Fatalf("expected forwarded roles, got %q", roles)
	}
}

func TestGatewayRateLimitRejectsBeforeProxy(t *testing.T) {
	upstreamHit := false
	transport := roundTripFunc(func(request *http.Request) (*http.Response, error) {
		upstreamHit = true
		return testResponse(http.StatusOK, ""), nil
	})

	logger := &captureAccessLogger{}
	router := newTestRouter(routerTestConfig{
		logger:    logger,
		transport: transport,
		limiter: staticLimiter{decision: domain.RateLimitDecision{
			Allowed:      false,
			Result:       "rejected",
			RejectReason: "service rate limit exceeded",
		}},
		now: time.Now,
	})

	response := httptest.NewRecorder()
	router.ServeHTTP(response, httptest.NewRequest(http.MethodPost, "/api/v1/account/login", nil))

	if response.Code != http.StatusTooManyRequests {
		t.Fatalf("expected 429, got %d", response.Code)
	}
	if upstreamHit {
		t.Fatal("rate limited request should not reach upstream")
	}
	metadata := logger.events[0].Metadata
	if metadata.RateLimitResult != "rejected" {
		t.Fatalf("unexpected rate limit result %q", metadata.RateLimitResult)
	}
}

func newTestRouter(config routerTestConfig) http.Handler {
	backendURL := config.backendURL
	if backendURL == "" {
		backendURL = "http://backend.local"
	}
	secret := config.secret
	if secret == "" {
		secret = "test-secret-with-at-least-32-bytes"
	}
	logger := config.logger
	if logger == nil {
		logger = &captureAccessLogger{}
	}
	now := config.now
	if now == nil {
		now = time.Now
	}
	location := config.location
	if location == nil {
		location = time.Local
	}

	pipeline := appgateway.NewPipeline(appgateway.PipelineConfig{
		ServiceName:     "icore-gateway",
		RoutePolicy:     appgateway.NewDefaultRoutePolicy(backendURL),
		RequestIDPolicy: domain.RequestIDPolicy{},
		IdentityPolicy:  appgateway.IdentityPolicy{},
		Location:        location,
		Now:             now,
	}, appgateway.PipelineDependencies{
		Authenticator: jwtinfra.NewAuthenticator(jwtinfra.Config{
			Secret:   secret,
			Issuer:   "icore-agent",
			Audience: "icore-gateway",
		}),
		Limiter:      config.limiter,
		Proxy:        proxyinfra.NewReverseProxy(backendURL, config.transport),
		AccessLogger: logger,
	})
	return NewRouter(NewHandler(pipeline))
}

func testResponse(status int, body string) *http.Response {
	return &http.Response{
		StatusCode: status,
		Status:     http.StatusText(status),
		Header:     make(http.Header),
		Body:       io.NopCloser(strings.NewReader(body)),
	}
}

func signTestJWT(t *testing.T, secret string, subject string, roles []string, expiresAt time.Time) string {
	t.Helper()
	claims := map[string]any{
		"sub":   subject,
		"roles": roles,
		"iss":   "icore-agent",
		"aud":   "icore-gateway",
		"iat":   time.Now().Unix(),
		"exp":   expiresAt.Unix(),
	}
	token, err := encodeTestJWT(claims, secret)
	if err != nil {
		t.Fatalf("sign test token: %v", err)
	}
	return token
}

func encodeTestJWT(claims map[string]any, secret string) (string, error) {
	header, err := json.Marshal(map[string]string{"alg": "HS256", "typ": "JWT"})
	if err != nil {
		return "", err
	}
	raw, err := json.Marshal(claims)
	if err != nil {
		return "", err
	}
	headerSegment := base64.RawURLEncoding.EncodeToString(header)
	payloadSegment := base64.RawURLEncoding.EncodeToString(raw)
	signingInput := headerSegment + "." + payloadSegment
	digest := hmac.New(sha256.New, []byte(secret))
	_, _ = digest.Write([]byte(signingInput))
	signature := base64.RawURLEncoding.EncodeToString(digest.Sum(nil))
	return signingInput + "." + signature, nil
}
