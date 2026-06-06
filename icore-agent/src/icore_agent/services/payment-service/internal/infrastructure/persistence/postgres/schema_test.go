package postgres

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestInitialMigrationUsesProviderNeutralPaymentSchema(t *testing.T) {
	content, err := os.ReadFile(filepath.Join("..", "..", "..", "..", "migrations", "000001_create_payment_orders.up.sql"))
	if err != nil {
		t.Fatalf("read migration: %v", err)
	}
	sql := string(content)

	for _, forbidden := range []string{
		"wechat_transaction_id",
		"wechat_trade_state",
		"code_url TEXT",
		"code_url_expires_at",
	} {
		if strings.Contains(sql, forbidden) {
			t.Fatalf("migration contains provider-specific order field %q", forbidden)
		}
	}
	for _, required := range []string{
		"CREATE TABLE IF NOT EXISTS payment_provider_transactions",
		"payment_payload JSONB NOT NULL DEFAULT '{}'::jsonb",
		"CONSTRAINT uq_payment_provider_transactions_merchant_order",
		"uq_payment_provider_transactions_provider_transaction",
		"merchant_order_no",
		"provider_transaction_id",
	} {
		if !strings.Contains(sql, required) {
			t.Fatalf("migration missing provider-neutral schema fragment %q", required)
		}
	}
}

func TestClaimPendingOutboxRecoversExpiredPublishingRows(t *testing.T) {
	source, err := os.ReadFile("repository.go")
	if err != nil {
		t.Fatalf("read repository.go: %v", err)
	}
	sql := string(source)

	if !strings.Contains(sql, "status = 'publishing'\n    AND next_attempt_at <= now()") {
		t.Fatalf("ClaimPendingOutbox must reclaim expired publishing rows")
	}
}
