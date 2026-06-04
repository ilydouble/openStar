package wechatpay

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"

	"icore-payment-service/internal/application/checkout"
	"icore-payment-service/internal/domain/payment"

	"github.com/wechatpay-apiv3/wechatpay-go/core"
	"github.com/wechatpay-apiv3/wechatpay-go/core/auth/verifiers"
	"github.com/wechatpay-apiv3/wechatpay-go/core/consts"
	"github.com/wechatpay-apiv3/wechatpay-go/core/notify"
	"github.com/wechatpay-apiv3/wechatpay-go/core/option"
	"github.com/wechatpay-apiv3/wechatpay-go/services/payments"
	"github.com/wechatpay-apiv3/wechatpay-go/services/payments/native"
	"github.com/wechatpay-apiv3/wechatpay-go/utils"
)

// Config contains WeChat Pay API credentials and endpoint settings.
type Config struct {
	AppID                    string
	MchID                    string
	MchCertificateSerialNo   string
	MchPrivateKeyPath        string
	APIv3Key                 string
	PublicKeyID              string
	PublicKeyPath            string
	NotifyURL                string
	APIHost                  string
	HTTPTimeout              time.Duration
	RequireProductionAPIHost bool
}

// NativeProvider adapts WeChat Pay Native SDK calls to payment-service ports.
type NativeProvider struct {
	appID    string
	mchID    string
	notify   *notify.Handler
	native   *native.NativeApiService
	apiV3Key string
}

// NewNativeProvider initializes a WeChat Pay Native provider using public-key verification.
func NewNativeProvider(ctx context.Context, config Config) (*NativeProvider, error) {
	if err := config.validate(); err != nil {
		return nil, err
	}
	privateKey, err := utils.LoadPrivateKeyWithPath(config.MchPrivateKeyPath)
	if err != nil {
		return nil, fmt.Errorf("load merchant private key: %w", err)
	}
	publicKey, err := utils.LoadPublicKeyWithPath(config.PublicKeyPath)
	if err != nil {
		return nil, fmt.Errorf("load wechatpay public key: %w", err)
	}
	httpClient, err := newHTTPClient(config)
	if err != nil {
		return nil, err
	}
	client, err := core.NewClient(
		ctx,
		option.WithHTTPClient(httpClient),
		option.WithWechatPayPublicKeyAuthCipher(
			config.MchID,
			config.MchCertificateSerialNo,
			privateKey,
			config.PublicKeyID,
			publicKey,
		),
	)
	if err != nil {
		return nil, fmt.Errorf("create wechatpay client: %w", err)
	}
	notifyHandler, err := notify.NewRSANotifyHandler(
		config.APIv3Key,
		verifiers.NewSHA256WithRSAPubkeyVerifier(config.PublicKeyID, *publicKey),
	)
	if err != nil {
		return nil, fmt.Errorf("create wechatpay notify handler: %w", err)
	}
	return &NativeProvider{
		appID:    config.AppID,
		mchID:    config.MchID,
		notify:   notifyHandler,
		native:   &native.NativeApiService{Client: client},
		apiV3Key: config.APIv3Key,
	}, nil
}

// PrepayNative calls WeChat Pay Native prepay and returns the QR code URL.
func (provider *NativeProvider) PrepayNative(ctx context.Context, request checkout.ProviderPrepayRequest) (checkout.ProviderPrepayResult, error) {
	response, _, err := provider.native.Prepay(ctx, native.PrepayRequest{
		Appid:       core.String(request.AppID),
		Mchid:       core.String(request.MchID),
		Description: core.String(request.Description),
		OutTradeNo:  core.String(request.OutTradeNo),
		TimeExpire:  core.Time(request.TimeExpire),
		Attach:      core.String(request.Attach),
		NotifyUrl:   core.String(request.NotifyURL),
		Amount: &native.Amount{
			Total:    core.Int64(request.AmountCents),
			Currency: core.String(request.Currency),
		},
	})
	if err != nil {
		return checkout.ProviderPrepayResult{}, err
	}
	if response == nil || response.CodeUrl == nil || strings.TrimSpace(*response.CodeUrl) == "" {
		return checkout.ProviderPrepayResult{}, fmt.Errorf("wechatpay prepay response missing code_url")
	}
	return checkout.ProviderPrepayResult{CodeURL: *response.CodeUrl}, nil
}

// CloseOrder calls WeChat Pay close order for an unpaid merchant order.
func (provider *NativeProvider) CloseOrder(ctx context.Context, outTradeNo string) error {
	_, err := provider.native.CloseOrder(ctx, native.CloseOrderRequest{
		OutTradeNo: core.String(outTradeNo),
		Mchid:      core.String(provider.mchID),
	})
	return err
}

// ParseNotification verifies and decrypts a WeChat Pay notification request.
func (provider *NativeProvider) ParseNotification(ctx context.Context, request *http.Request) (payment.ProviderNotification, error) {
	transaction := new(payments.Transaction)
	notifyRequest, err := provider.notify.ParseNotifyRequest(ctx, request, transaction)
	if err != nil {
		return payment.ProviderNotification{}, err
	}
	return payment.ProviderNotification{
		EventID:   notifyRequest.ID,
		EventType: notifyRequest.EventType,
		Transaction: payment.ProviderTransaction{
			AppID:         stringValue(transaction.Appid),
			MchID:         stringValue(transaction.Mchid),
			OutTradeNo:    stringValue(transaction.OutTradeNo),
			TransactionID: stringValue(transaction.TransactionId),
			TradeState:    stringValue(transaction.TradeState),
			Currency:      transactionCurrency(transaction),
			AmountCents:   transactionAmount(transaction),
			SuccessTime:   parseWechatPayTime(transaction.SuccessTime),
		},
		RawPayload: []byte(notifyRequest.Resource.Plaintext),
	}, nil
}

func (config Config) validate() error {
	required := map[string]string{
		"WECHATPAY_APP_ID":               config.AppID,
		"WECHATPAY_MCH_ID":               config.MchID,
		"WECHATPAY_MCH_CERT_SERIAL_NO":   config.MchCertificateSerialNo,
		"WECHATPAY_MCH_PRIVATE_KEY_PATH": config.MchPrivateKeyPath,
		"WECHATPAY_API_V3_KEY":           config.APIv3Key,
		"WECHATPAY_PUBLIC_KEY_ID":        config.PublicKeyID,
		"WECHATPAY_PUBLIC_KEY_PATH":      config.PublicKeyPath,
		"WECHATPAY_NOTIFY_URL":           config.NotifyURL,
	}
	for name, value := range required {
		if strings.TrimSpace(value) == "" {
			return fmt.Errorf("%s is required", name)
		}
	}
	if config.RequireProductionAPIHost && strings.TrimSpace(config.APIHost) != "" && strings.TrimRight(config.APIHost, "/") != consts.WechatPayAPIServer {
		return fmt.Errorf("WECHATPAY_API_HOST must be %s when WECHATPAY_REQUIRE_PRODUCTION_HOST=true", consts.WechatPayAPIServer)
	}
	return nil
}

func newHTTPClient(config Config) (*http.Client, error) {
	timeout := config.HTTPTimeout
	if timeout <= 0 {
		timeout = 10 * time.Second
	}
	transport := http.DefaultTransport
	apiHost := strings.TrimSpace(config.APIHost)
	if apiHost != "" && strings.TrimRight(apiHost, "/") != consts.WechatPayAPIServer {
		parsed, err := url.Parse(apiHost)
		if err != nil {
			return nil, fmt.Errorf("parse WECHATPAY_API_HOST: %w", err)
		}
		transport = newAPIHostRewriteTransport(transport, parsed)
	}
	return &http.Client{Timeout: timeout, Transport: transport}, nil
}

type apiHostRewriteTransport struct {
	base   http.RoundTripper
	target *url.URL
}

func newAPIHostRewriteTransport(base http.RoundTripper, target *url.URL) http.RoundTripper {
	if base == nil {
		base = http.DefaultTransport
	}
	return apiHostRewriteTransport{base: base, target: target}
}

func (transport apiHostRewriteTransport) RoundTrip(request *http.Request) (*http.Response, error) {
	if transport.target != nil && strings.EqualFold(request.URL.Host, "api.mch.weixin.qq.com") {
		cloned := request.Clone(request.Context())
		cloned.URL.Scheme = transport.target.Scheme
		cloned.URL.Host = transport.target.Host
		cloned.Host = transport.target.Host
		return transport.base.RoundTrip(cloned)
	}
	return transport.base.RoundTrip(request)
}

func stringValue(value *string) string {
	if value == nil {
		return ""
	}
	return *value
}

func transactionAmount(transaction *payments.Transaction) int64 {
	if transaction == nil || transaction.Amount == nil || transaction.Amount.Total == nil {
		return 0
	}
	return *transaction.Amount.Total
}

func transactionCurrency(transaction *payments.Transaction) string {
	if transaction == nil || transaction.Amount == nil || transaction.Amount.Currency == nil {
		return ""
	}
	return *transaction.Amount.Currency
}

func parseWechatPayTime(value *string) *time.Time {
	if value == nil || strings.TrimSpace(*value) == "" {
		return nil
	}
	parsed, err := time.Parse(time.RFC3339, *value)
	if err != nil {
		return nil
	}
	return &parsed
}
