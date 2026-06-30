package paymentlog

import (
	"errors"
	"testing"

	"icore-payment-service/internal/domain/payment"
)

func TestProviderMetadataFromErrorWrapsProviderDetails(t *testing.T) {
	err := &payment.ProviderError{
		Provider:       payment.ProviderWeChatPay,
		API:            "native.prepay",
		HTTPStatus:     403,
		Code:           "NO_AUTH",
		Message:        "merchant payment function is limited",
		RequestID:      "request-id",
		ResponseSerial: "serial-no",
	}

	metadata := ProviderMetadataFromError(payment.ProviderWeChatPay, "merchant-1", "native.prepay", err)

	if metadata.Name != payment.ProviderWeChatPay || metadata.MerchantID != "merchant-1" || metadata.API != "native.prepay" {
		t.Fatalf("provider metadata identity = %#v", metadata)
	}
	if metadata.RequestID != "request-id" || metadata.ResponseSerial != "serial-no" {
		t.Fatalf("provider correlation metadata = %#v", metadata)
	}
	if metadata.Error == nil || metadata.Error.HTTPStatus != 403 || metadata.Error.Code != "NO_AUTH" {
		t.Fatalf("provider error metadata = %#v", metadata.Error)
	}
}

func TestProviderMetadataFromErrorKeepsGenericErrorProviderNeutral(t *testing.T) {
	metadata := ProviderMetadataFromError(payment.ProviderWeChatPay, "merchant-1", "native.prepay", errors.New("temporary network error"))

	if metadata.Name != payment.ProviderWeChatPay || metadata.API != "native.prepay" {
		t.Fatalf("provider metadata identity = %#v", metadata)
	}
	if metadata.Error == nil || metadata.Error.Message != "temporary network error" {
		t.Fatalf("provider error metadata = %#v", metadata.Error)
	}
	if metadata.RequestID != "" || metadata.ResponseSerial != "" {
		t.Fatalf("provider correlation metadata = %#v", metadata)
	}
}
