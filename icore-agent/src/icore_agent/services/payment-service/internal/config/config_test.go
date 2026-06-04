package config

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
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

func writeCatalogFile(t *testing.T, content string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "catalog_json.config")
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatalf("write catalog file: %v", err)
	}
	return path
}
