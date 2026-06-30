package payment

import "fmt"

const (
	// ProviderWeChatPay is the provider name used for WeChat Pay integrations.
	ProviderWeChatPay = "wechatpay"
	// PaymentMethodNative is the provider method for QR-code Native payments.
	PaymentMethodNative = "native"
)

// ProviderError describes a failed provider operation without exposing SDK-specific details to callers.
type ProviderError struct {
	Provider       string `json:"provider"`
	API            string `json:"api"`
	HTTPStatus     int    `json:"http_status,omitempty"`
	Code           string `json:"code,omitempty"`
	Message        string `json:"message,omitempty"`
	RequestID      string `json:"request_id,omitempty"`
	ResponseSerial string `json:"response_serial,omitempty"`
	Err            error  `json:"-"`
}

// Error returns a safe provider failure summary.
func (err *ProviderError) Error() string {
	if err == nil {
		return "payment provider error"
	}
	if err.Code != "" && err.Message != "" {
		return fmt.Sprintf("%s %s failed: %s %s", err.Provider, err.API, err.Code, err.Message)
	}
	if err.Message != "" {
		return fmt.Sprintf("%s %s failed: %s", err.Provider, err.API, err.Message)
	}
	return fmt.Sprintf("%s %s failed", err.Provider, err.API)
}

// Unwrap returns the underlying provider or SDK error.
func (err *ProviderError) Unwrap() error {
	if err == nil {
		return nil
	}
	return err.Err
}
