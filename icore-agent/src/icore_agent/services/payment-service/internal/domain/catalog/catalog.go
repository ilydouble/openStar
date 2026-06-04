package catalog

import (
	"encoding/json"
	"fmt"
	"strings"
)

// Item describes one payable plan-price entry owned by payment-service.
type Item struct {
	PlanCode            string `json:"plan_code"`
	BillingPeriod       string `json:"billing_period"`
	Currency            string `json:"currency"`
	AmountCents         int64  `json:"amount_cents"`
	Description         string `json:"description"`
	EntitlementsVersion string `json:"entitlements_version"`
	Enabled             bool   `json:"enabled"`
}

// Catalog stores enabled payment catalog items keyed by plan and billing period.
type Catalog struct {
	items map[string]Item
}

type catalogJSON struct {
	Items []Item `json:"items"`
}

// NewCatalog validates and indexes payment catalog items.
func NewCatalog(items []Item) (Catalog, error) {
	indexed := make(map[string]Item, len(items))
	for _, item := range items {
		normalized, err := normalizeItem(item)
		if err != nil {
			return Catalog{}, err
		}
		key := catalogKey(normalized.PlanCode, normalized.BillingPeriod)
		if _, exists := indexed[key]; exists {
			return Catalog{}, fmt.Errorf("duplicate catalog item %s %s", normalized.PlanCode, normalized.BillingPeriod)
		}
		indexed[key] = normalized
	}
	return Catalog{items: indexed}, nil
}

// ParseJSON parses the PAYMENT_CATALOG_JSON document.
func ParseJSON(raw string) (Catalog, error) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return Catalog{}, fmt.Errorf("PAYMENT_CATALOG_JSON is required")
	}
	var payload catalogJSON
	if err := json.Unmarshal([]byte(raw), &payload); err != nil {
		return Catalog{}, fmt.Errorf("parse PAYMENT_CATALOG_JSON: %w", err)
	}
	if len(payload.Items) == 0 {
		return Catalog{}, fmt.Errorf("PAYMENT_CATALOG_JSON must contain at least one item")
	}
	return NewCatalog(payload.Items)
}

// Find returns an enabled catalog item for the plan and billing period.
func (catalog Catalog) Find(planCode string, billingPeriod string) (Item, bool) {
	item, ok := catalog.items[catalogKey(planCode, billingPeriod)]
	if !ok || !item.Enabled {
		return Item{}, false
	}
	return item, true
}

// ValidateRequiredMonthlyPlans verifies that the configured catalog has required monthly plans.
func (catalog Catalog) ValidateRequiredMonthlyPlans(planCodes []string) error {
	for _, planCode := range planCodes {
		if _, ok := catalog.Find(planCode, "monthly"); !ok {
			return fmt.Errorf("payment catalog missing enabled %s monthly item", planCode)
		}
	}
	return nil
}

func normalizeItem(item Item) (Item, error) {
	item.PlanCode = strings.TrimSpace(item.PlanCode)
	item.BillingPeriod = strings.TrimSpace(item.BillingPeriod)
	item.Currency = strings.ToUpper(strings.TrimSpace(item.Currency))
	item.Description = strings.TrimSpace(item.Description)
	item.EntitlementsVersion = strings.TrimSpace(item.EntitlementsVersion)

	if item.PlanCode == "" {
		return Item{}, fmt.Errorf("catalog item plan_code is required")
	}
	if item.BillingPeriod == "" {
		return Item{}, fmt.Errorf("catalog item billing_period is required")
	}
	if len(item.Currency) != 3 {
		return Item{}, fmt.Errorf("catalog item %s %s currency must be ISO-4217 code", item.PlanCode, item.BillingPeriod)
	}
	if item.AmountCents <= 0 {
		return Item{}, fmt.Errorf("catalog item %s %s amount_cents must be positive", item.PlanCode, item.BillingPeriod)
	}
	if item.Description == "" {
		return Item{}, fmt.Errorf("catalog item %s %s description is required", item.PlanCode, item.BillingPeriod)
	}
	if item.EntitlementsVersion == "" {
		return Item{}, fmt.Errorf("catalog item %s %s entitlements_version is required", item.PlanCode, item.BillingPeriod)
	}
	return item, nil
}

func catalogKey(planCode string, billingPeriod string) string {
	return strings.TrimSpace(planCode) + ":" + strings.TrimSpace(billingPeriod)
}
