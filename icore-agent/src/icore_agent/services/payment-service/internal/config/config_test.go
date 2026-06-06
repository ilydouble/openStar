package config

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"icore-payment-service/internal/domain/catalog"
)

func TestLoadRequiresPaymentCatalogJSONPath(t *testing.T) {
	t.Setenv("PAYMENT_DATABASE_URL", "postgres://icore_payment:secret@postgres:5432/icore_payment_db?sslmode=disable&search_path=payment")

	_, err := Load()
	if err == nil {
		t.Fatal("Load returned nil error, want PAYMENT_CATALOG_JSON_PATH error")
	}
	if !strings.Contains(err.Error(), "PAYMENT_CATALOG_JSON_PATH") {
		t.Fatalf("error = %q, want PAYMENT_CATALOG_JSON_PATH", err.Error())
	}
}

func TestLoadFailsWhenPaymentCatalogJSONPathCannotBeRead(t *testing.T) {
	t.Setenv("PAYMENT_DATABASE_URL", "postgres://icore_payment:secret@postgres:5432/icore_payment_db?sslmode=disable&search_path=payment")
	t.Setenv("PAYMENT_CATALOG_JSON_PATH", filepath.Join(t.TempDir(), "missing-catalog.json"))

	_, err := Load()
	if err == nil {
		t.Fatal("Load returned nil error, want missing catalog file error")
	}
	if !strings.Contains(err.Error(), "read PAYMENT_CATALOG_JSON_PATH") {
		t.Fatalf("error = %q, want read PAYMENT_CATALOG_JSON_PATH", err.Error())
	}
}

func TestLoadParsesRequiredMonthlyCatalog(t *testing.T) {
	t.Setenv("PAYMENT_DATABASE_URL", "postgres://icore_payment:secret@postgres:5432/icore_payment_db?sslmode=disable&search_path=payment")
	t.Setenv("PAYMENT_CATALOG_JSON_PATH", writeCatalogFile(t, `{
		"items": [
			{"plan_code":"pro","billing_period":"monthly","currency":"CNY","amount_cents":19900,"description":"Pro monthly","entitlements_version":"account-plans-v2","enabled":true},
			{"plan_code":"team","billing_period":"monthly","currency":"CNY","amount_cents":69900,"description":"Team monthly","entitlements_version":"account-plans-v2","enabled":true},
			{"plan_code":"premium","billing_period":"monthly","currency":"CNY","amount_cents":199900,"description":"Premium monthly","entitlements_version":"account-plans-v2","enabled":true},
			{"plan_code":"byok","billing_period":"monthly","currency":"CNY","amount_cents":6900,"description":"BYOK monthly","entitlements_version":"account-plans-v2","enabled":true}
		]
	}`))
	t.Setenv("WECHATPAY_APP_ID", "wx-app")
	t.Setenv("WECHATPAY_MCH_ID", "mch-1")
	t.Setenv("WECHATPAY_NOTIFY_URL", "https://pay.example.com/webhooks/wechatpay/native")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load returned error: %v", err)
	}

	item, ok := cfg.Catalog.Find("pro", "monthly")
	if !ok {
		t.Fatal("catalog missing pro monthly item")
	}
	if item.AmountCents != 19900 || item.Currency != "CNY" || item.EntitlementsVersion != "account-plans-v2" {
		t.Fatalf("catalog item = %#v", item)
	}
	if cfg.WeChatPay.AppID != "wx-app" || cfg.WeChatPay.MchID != "mch-1" {
		t.Fatalf("wechat config = %#v", cfg.WeChatPay)
	}
	if cfg.LoggingServiceName != "payment-service" || cfg.LoggingServiceTimeout.String() != "2s" || cfg.LoggingQueueSize != 4096 {
		t.Fatalf("logging defaults = name:%q timeout:%s queue:%d", cfg.LoggingServiceName, cfg.LoggingServiceTimeout, cfg.LoggingQueueSize)
	}
}

func TestLoadParsesPaymentLoggingConfig(t *testing.T) {
	t.Setenv("PAYMENT_DATABASE_URL", "postgres://icore_payment:secret@postgres:5432/icore_payment_db?sslmode=disable&search_path=payment")
	t.Setenv("PAYMENT_CATALOG_JSON_PATH", writeCatalogFile(t, `{
		"items": [
			{"plan_code":"pro","billing_period":"monthly","currency":"CNY","amount_cents":19900,"description":"Pro monthly","entitlements_version":"account-plans-v2","enabled":true},
			{"plan_code":"team","billing_period":"monthly","currency":"CNY","amount_cents":69900,"description":"Team monthly","entitlements_version":"account-plans-v2","enabled":true},
			{"plan_code":"premium","billing_period":"monthly","currency":"CNY","amount_cents":199900,"description":"Premium monthly","entitlements_version":"account-plans-v2","enabled":true},
			{"plan_code":"byok","billing_period":"monthly","currency":"CNY","amount_cents":6900,"description":"BYOK monthly","entitlements_version":"account-plans-v2","enabled":true}
		]
	}`))
	t.Setenv("LOGGING_SERVICE_URL", "http://logging-service:8091")
	t.Setenv("LOGGING_SERVICE_TOKEN", "dev-token")
	t.Setenv("PAYMENT_LOGGING_SERVICE_NAME", "payment-service-dev")
	t.Setenv("PAYMENT_LOGGING_SERVICE_TIMEOUT", "3s")
	t.Setenv("PAYMENT_LOGGING_QUEUE_SIZE", "512")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load returned error: %v", err)
	}

	if cfg.LoggingServiceURL != "http://logging-service:8091" || cfg.LoggingServiceToken != "dev-token" {
		t.Fatalf("logging target = url:%q token:%q", cfg.LoggingServiceURL, cfg.LoggingServiceToken)
	}
	if cfg.LoggingServiceName != "payment-service-dev" || cfg.LoggingServiceTimeout.String() != "3s" || cfg.LoggingQueueSize != 512 {
		t.Fatalf("payment logging config = name:%q timeout:%s queue:%d", cfg.LoggingServiceName, cfg.LoggingServiceTimeout, cfg.LoggingQueueSize)
	}
}

func TestLoadParsesNumericDurationWithSharedEnvconfig(t *testing.T) {
	t.Setenv("PAYMENT_DATABASE_URL", "postgres://icore_payment:secret@postgres:5432/icore_payment_db?sslmode=disable&search_path=payment")
	t.Setenv("PAYMENT_CATALOG_JSON_PATH", writeCatalogFile(t, `{
		"items": [
			{"plan_code":"pro","billing_period":"monthly","currency":"CNY","amount_cents":19900,"description":"Pro monthly","entitlements_version":"account-plans-v2","enabled":true},
			{"plan_code":"team","billing_period":"monthly","currency":"CNY","amount_cents":69900,"description":"Team monthly","entitlements_version":"account-plans-v2","enabled":true},
			{"plan_code":"premium","billing_period":"monthly","currency":"CNY","amount_cents":199900,"description":"Premium monthly","entitlements_version":"account-plans-v2","enabled":true},
			{"plan_code":"byok","billing_period":"monthly","currency":"CNY","amount_cents":6900,"description":"BYOK monthly","entitlements_version":"account-plans-v2","enabled":true}
		]
	}`))
	t.Setenv("PAYMENT_ORDER_TTL", "45")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load returned error: %v", err)
	}

	if cfg.OrderTTL.String() != "45s" {
		t.Fatalf("OrderTTL = %s, want 45s", cfg.OrderTTL)
	}
}

func TestLoadRejectsCatalogMissingRequiredPlan(t *testing.T) {
	t.Setenv("PAYMENT_DATABASE_URL", "postgres://icore_payment:secret@postgres:5432/icore_payment_db?sslmode=disable&search_path=payment")
	t.Setenv("PAYMENT_CATALOG_JSON_PATH", writeCatalogFile(t, `{
		"items": [
			{"plan_code":"pro","billing_period":"monthly","currency":"CNY","amount_cents":19900,"description":"Pro monthly","entitlements_version":"account-plans-v2","enabled":true}
		]
	}`))

	_, err := Load()
	if err == nil {
		t.Fatal("Load returned nil error, want missing plan error")
	}
	if !strings.Contains(err.Error(), "team monthly") {
		t.Fatalf("error = %q, want team monthly", err.Error())
	}
}

func TestPlanItemsConfigFileContainsRequiredMonthlyCatalog(t *testing.T) {
	content, err := os.ReadFile(filepath.Join("..", "..", "config", "catalog", "plan_items.json"))
	if err != nil {
		t.Fatalf("read plan_items.json: %v", err)
	}
	cat, err := catalog.ParseJSON(string(content))
	if err != nil {
		t.Fatalf("parse plan_items.json: %v", err)
	}
	if err := cat.ValidateRequiredMonthlyPlans([]string{"pro", "team", "premium", "byok"}); err != nil {
		t.Fatalf("validate plan_items.json: %v", err)
	}
}

func writeCatalogFile(t *testing.T, content string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "plan_items.json")
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatalf("write catalog file: %v", err)
	}
	return path
}
