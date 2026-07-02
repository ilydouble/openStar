# Commerce OS V1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the first visible iCore Commerce OS prototype: a commerce-focused landing page, an authenticated operations dashboard, sample commerce data, CSV import scaffolding, AI daily brief generation, and a task center.

**Architecture:** Keep the current iCore account, Agent, payment, gateway, and file foundations. Add a new `commerce` business domain owned by the Python backend, with all commerce records scoped by `organization_id` from day one. The first UI should feel like a single-team pilot, but the backend should avoid single-user assumptions so it can grow into multi-team SaaS later.

**Tech Stack:** Vue/Vite frontend, FastAPI HTTP v1 API, SQLAlchemy models/repositories, Alembic migrations, PostgreSQL, existing `ApiEnvelope`, existing Python Agent as analysis/orchestration layer.

---

## Product Scope

### V1 Must Look Like

The first version should make iCore look like a real commerce operations product, even before deep Shopify/Amazon integrations exist.

V1 should show:

- A commerce-focused public landing page.
- A logged-in operations dashboard.
- KPI cards for sales, gross margin, inventory risk, order exceptions, supplier follow-ups, and AI recommendations.
- Sample commerce data for demo mode.
- CSV import entry points for products, orders, inventory, and suppliers.
- A Daily Brief page that summarizes business health and next actions.
- A task center showing AI-suggested operational tasks.
- A right-side AI assistant framed as an operations copilot, not a generic chat bot.

### V1 Should Not Build

- Full ERP.
- Full accounting.
- Automatic refunds.
- Automatic price changes.
- Deep Amazon SP-API integration.
- Deep Shopify production OAuth.
- Multi-warehouse WMS.
- Complex RBAC beyond owner/operator/viewer.
- Pi Agent routing for commerce. Pi remains code-project analysis only.

---

## Single-Team vs Multi-Team Decision

### Recommended Product Experience

V1 should feel like a single-team pilot:

- One organization workspace after login.
- One commerce dashboard.
- Sample data can be loaded instantly.
- CSV import is the primary data onboarding path.
- UI avoids complex tenant switchers unless already present in account/team areas.

This keeps the product understandable for ads and demos.

### Required Technical Foundation

Even though the UI feels single-team, every commerce record must be scoped to an organization:

- `organization_id`
- `created_by`
- `created_at`
- `updated_at`

This lets iCore later support:

- Multiple teams.
- Multiple users per team.
- Multiple stores/channels per organization.
- Team-scoped permissions.
- SaaS billing by organization.

Do not create commerce data scoped only by `user_id`. Use `user_id` for ownership/audit, not tenancy.

---

## Milestone 1: Product Shell and Landing Page

**Goal:** Reposition the product visually from generic AI workspace to Commerce OS.

### Task 1: Create Commerce Route Shell

**Files:**

- Modify: `icore-agent-web/src/router.js`
- Create: `icore-agent-web/src/views/CommerceDashboardView.vue`
- Create: `icore-agent-web/src/components/commerce/CommerceShell.vue`
- Create: `icore-agent-web/src/components/commerce/CommerceSidebar.vue`

**Steps:**

1. Add authenticated route `/commerce` named `commerce`.
2. Keep `/app` as the existing generic workspace during transition.
3. Build `CommerceShell` with left navigation and a main content slot.
4. Add navigation items: Dashboard, Daily Brief, Tasks, Products, Inventory, Suppliers, Orders, Support, Data Import.
5. Add a right-side AI assistant placeholder panel titled "AI Operations Assistant".

**Verification:**

- Run `npm test`.
- Run `npm run build`.
- Visit `/commerce` in dev server and confirm route renders for authenticated session.

**Commit:**

```bash
git add icore-agent-web/src/router.js icore-agent-web/src/views/CommerceDashboardView.vue icore-agent-web/src/components/commerce/CommerceShell.vue icore-agent-web/src/components/commerce/CommerceSidebar.vue
git commit -m "Add Commerce OS app shell"
```

### Task 2: Rework Public Landing Message

**Files:**

- Modify: `icore-agent-web/src/views/LandingView.vue`
- Modify: `icore-agent-web/src/components/landing/HeroSection.vue`
- Modify: `icore-agent-web/src/components/landing/SignalsSection.vue`
- Modify: `icore-agent-web/src/components/landing/SolutionsSection.vue`

**Content Requirements:**

- Primary headline: "AI operations dashboard for small cross-border commerce teams."
- Primary CTA: "View sample operations brief".
- Secondary CTA: "Upload CSV for a free diagnosis".
- Page should show product value, not generic AI capability.

**Verification:**

- Run `npm test`.
- Run `npm run build`.
- Check desktop and mobile layout manually.

**Commit:**

```bash
git add icore-agent-web/src/views/LandingView.vue icore-agent-web/src/components/landing/HeroSection.vue icore-agent-web/src/components/landing/SignalsSection.vue icore-agent-web/src/components/landing/SolutionsSection.vue
git commit -m "Position landing page for Commerce OS"
```

---

## Milestone 2: Commerce Domain Backend Skeleton

**Goal:** Add backend domain boundaries before UI depends on data.

### Task 3: Add Commerce Domain Package

**Files:**

- Create: `icore-agent/src/icore_agent/domain/commerce/__init__.py`
- Create: `icore-agent/src/icore_agent/domain/commerce/models.py`
- Create: `icore-agent/src/icore_agent/application/commerce/__init__.py`
- Create: `icore-agent/src/icore_agent/application/commerce/service.py`
- Create: `icore-agent/src/icore_agent/infrastructure/persistence/commerce/__init__.py`
- Create: `icore-agent/src/icore_agent/infrastructure/persistence/commerce/models.py`
- Create: `icore-agent/src/icore_agent/infrastructure/persistence/commerce/repository.py`

**Domain Entities:**

- Product/SKU
- InventorySnapshot
- Supplier
- OrderSummary
- CommerceTask
- DailyBrief

**Rules:**

- Domain models should be dataclasses or Pydantic-free plain domain objects.
- SQLAlchemy stays under infrastructure.
- HTTP schemas stay under interfaces.
- All persistence models include `organization_id`.

**Verification:**

- Add unit tests under `icore-agent/tests/unit/test_commerce_domain.py`.
- Run `icore-agent/.venv/bin/autopep8 -i` on changed Python files.
- Run `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest tests/unit/test_commerce_domain.py`.

**Commit:**

```bash
git add icore-agent/src/icore_agent/domain/commerce icore-agent/src/icore_agent/application/commerce icore-agent/src/icore_agent/infrastructure/persistence/commerce icore-agent/tests/unit/test_commerce_domain.py
git commit -m "Add Commerce OS domain skeleton"
```

### Task 4: Add Commerce Alembic Migration

**Files:**

- Create: `icore-agent/alembic/versions/0015_create_commerce_tables.py`
- Modify: `icore-agent/src/icore_agent/infrastructure/persistence/sqlalchemy/models.py`

**Tables:**

- `commerce_products`
- `commerce_suppliers`
- `commerce_inventory_snapshots`
- `commerce_order_summaries`
- `commerce_tasks`
- `commerce_daily_briefs`

**Migration Requirements:**

- Every table has `organization_id`.
- Add indexes for `organization_id`, `sku`, `status`, and date fields.
- Foreign key to `organizations.public_id` or existing organization primary strategy must match local repository conventions.

**Verification:**

- Add/extend scaffolding test in `icore-agent/tests/test_project_scaffolding.py`.
- Run migration tests if present.
- Run full backend pytest after this milestone.

**Commit:**

```bash
git add icore-agent/alembic/versions/0015_create_commerce_tables.py icore-agent/src/icore_agent/infrastructure/persistence/sqlalchemy/models.py icore-agent/tests/test_project_scaffolding.py
git commit -m "Add Commerce OS database tables"
```

---

## Milestone 3: Demo Data and Read APIs

**Goal:** Make the dashboard usable before CSV import exists.

### Task 5: Add Commerce HTTP Router

**Files:**

- Create: `icore-agent/src/icore_agent/interfaces/http/v1/commerce/__init__.py`
- Create: `icore-agent/src/icore_agent/interfaces/http/v1/commerce/router.py`
- Create: `icore-agent/src/icore_agent/interfaces/http/v1/commerce/handlers.py`
- Create: `icore-agent/src/icore_agent/interfaces/http/v1/commerce/schemas.py`
- Modify: `icore-agent/src/icore_agent/interfaces/http/v1/router.py`
- Modify: `icore-agent/src/icore_agent/interfaces/http/v1/dependencies.py`

**Endpoints:**

- `GET /api/v1/commerce/overview`
- `GET /api/v1/commerce/products`
- `GET /api/v1/commerce/inventory/risks`
- `GET /api/v1/commerce/suppliers`
- `GET /api/v1/commerce/tasks`
- `GET /api/v1/commerce/daily-brief`

**Rules:**

- Use existing `ApiEnvelope`.
- Resolve organization from authenticated user/team context.
- Service clients must read business fields from `data`, not top-level envelope.

**Verification:**

- Add tests under `icore-agent/tests/test_commerce_api.py`.
- Run `env PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest tests/test_commerce_api.py`.

**Commit:**

```bash
git add icore-agent/src/icore_agent/interfaces/http/v1/commerce icore-agent/src/icore_agent/interfaces/http/v1/router.py icore-agent/src/icore_agent/interfaces/http/v1/dependencies.py icore-agent/tests/test_commerce_api.py
git commit -m "Expose Commerce OS read APIs"
```

### Task 6: Add Demo Dataset Service

**Files:**

- Create: `icore-agent/src/icore_agent/application/commerce/demo_data.py`
- Modify: `icore-agent/src/icore_agent/application/commerce/service.py`
- Modify: `icore-agent/src/icore_agent/interfaces/http/v1/commerce/handlers.py`
- Test: `icore-agent/tests/unit/test_commerce_demo_data.py`

**Behavior:**

- If an organization has no commerce data, API can return deterministic demo data when `demo=true`.
- Demo data should include 8-12 SKUs, 3 suppliers, several inventory risks, and a daily brief.
- Demo mode must be explicit so real users do not confuse sample data with their own data.

**Verification:**

- Run focused demo data tests.
- Run commerce API tests.

**Commit:**

```bash
git add icore-agent/src/icore_agent/application/commerce/demo_data.py icore-agent/src/icore_agent/application/commerce/service.py icore-agent/src/icore_agent/interfaces/http/v1/commerce/handlers.py icore-agent/tests/unit/test_commerce_demo_data.py
git commit -m "Add Commerce OS demo dataset"
```

---

## Milestone 4: Dashboard UI With Demo Data

**Goal:** The deployed product should look like a useful commerce cockpit.

### Task 7: Add Frontend Commerce API Client

**Files:**

- Create: `icore-agent-web/src/api/commerce.js`
- Create: `icore-agent-web/src/api/commerce.test.js`

**Functions:**

- `fetchCommerceOverview({ demo })`
- `fetchCommerceProducts({ demo })`
- `fetchInventoryRisks({ demo })`
- `fetchSuppliers({ demo })`
- `fetchCommerceTasks({ demo })`
- `fetchDailyBrief({ demo })`

**Verification:**

- Tests assert ApiEnvelope unwrapping.
- Tests assert useful errors via existing `formatApiErrorMessage`.
- Run `npm test`.

**Commit:**

```bash
git add icore-agent-web/src/api/commerce.js icore-agent-web/src/api/commerce.test.js
git commit -m "Add Commerce OS frontend API client"
```

### Task 8: Build Dashboard Cards and Lists

**Files:**

- Modify: `icore-agent-web/src/views/CommerceDashboardView.vue`
- Create: `icore-agent-web/src/components/commerce/MetricCard.vue`
- Create: `icore-agent-web/src/components/commerce/RiskSkuTable.vue`
- Create: `icore-agent-web/src/components/commerce/CommerceTaskList.vue`
- Create: `icore-agent-web/src/components/commerce/DailyBriefPanel.vue`

**UI Requirements:**

- SaaS dashboard style, dense and operational.
- No decorative hero layout inside app.
- Cards use radius 8px or less.
- Use stable dimensions for KPI cards and tables.
- Keep AI assistant as a contextual side panel.

**Verification:**

- Run `npm test`.
- Run `npm run build`.
- Manual visual check desktop and mobile.

**Commit:**

```bash
git add icore-agent-web/src/views/CommerceDashboardView.vue icore-agent-web/src/components/commerce/MetricCard.vue icore-agent-web/src/components/commerce/RiskSkuTable.vue icore-agent-web/src/components/commerce/CommerceTaskList.vue icore-agent-web/src/components/commerce/DailyBriefPanel.vue
git commit -m "Build Commerce OS dashboard UI"
```

---

## Milestone 5: CSV Import MVP

**Goal:** Let a real prospect upload lightweight data and see a diagnosis.

### Task 9: Add CSV Import Backend

**Files:**

- Create: `icore-agent/src/icore_agent/application/commerce/imports.py`
- Modify: `icore-agent/src/icore_agent/interfaces/http/v1/commerce/handlers.py`
- Modify: `icore-agent/src/icore_agent/interfaces/http/v1/commerce/router.py`
- Test: `icore-agent/tests/unit/test_commerce_imports.py`
- Test: `icore-agent/tests/test_commerce_import_api.py`

**Endpoint:**

- `POST /api/v1/commerce/imports/csv`

**Supported import types:**

- `products`
- `orders`
- `inventory`
- `suppliers`

**Rules:**

- Validate headers.
- Reject oversized CSV files.
- Return row-level validation errors.
- Do not persist partial imports unless explicitly requested.
- Scope imported records to organization.

**Verification:**

- Run import unit tests.
- Run import API tests.
- Run backend full pytest after milestone.

**Commit:**

```bash
git add icore-agent/src/icore_agent/application/commerce/imports.py icore-agent/src/icore_agent/interfaces/http/v1/commerce icore-agent/tests/unit/test_commerce_imports.py icore-agent/tests/test_commerce_import_api.py
git commit -m "Add Commerce OS CSV import API"
```

### Task 10: Add Data Import UI

**Files:**

- Create: `icore-agent-web/src/views/CommerceImportView.vue`
- Modify: `icore-agent-web/src/router.js`
- Modify: `icore-agent-web/src/api/commerce.js`
- Create: `icore-agent-web/src/components/commerce/CsvImportPanel.vue`

**UI Requirements:**

- Four import cards: Products, Orders, Inventory, Suppliers.
- Show required columns before upload.
- Show validation results after upload.
- Provide "Load sample data" action.

**Verification:**

- Add frontend tests for API client upload call shape.
- Run `npm test`.
- Run `npm run build`.

**Commit:**

```bash
git add icore-agent-web/src/views/CommerceImportView.vue icore-agent-web/src/router.js icore-agent-web/src/api/commerce.js icore-agent-web/src/components/commerce/CsvImportPanel.vue
git commit -m "Add Commerce OS CSV import UI"
```

---

## Milestone 6: AI Daily Brief and Task Generation

**Goal:** Turn data into AI-generated operational recommendations.

### Task 11: Add Daily Brief Generator

**Files:**

- Create: `icore-agent/src/icore_agent/application/commerce/briefing.py`
- Modify: `icore-agent/src/icore_agent/application/commerce/service.py`
- Test: `icore-agent/tests/unit/test_commerce_briefing.py`

**Behavior:**

- Generate deterministic rule-based brief first.
- Include AI-generated narrative only behind a service method that can be mocked.
- Compute:
  - Sales summary.
  - Margin warnings.
  - Inventory risks.
  - Supplier follow-ups.
  - Today priorities.

**Why rule-based first:**

V1 needs reliable output before LLM polish. The AI can rewrite and explain, but the facts should come from deterministic analytics.

**Verification:**

- Run briefing tests.
- Run commerce API tests.

**Commit:**

```bash
git add icore-agent/src/icore_agent/application/commerce/briefing.py icore-agent/src/icore_agent/application/commerce/service.py icore-agent/tests/unit/test_commerce_briefing.py
git commit -m "Generate Commerce OS daily briefs"
```

### Task 12: Add AI-Suggested Task Creation

**Files:**

- Create: `icore-agent/src/icore_agent/application/commerce/task_generation.py`
- Modify: `icore-agent/src/icore_agent/application/commerce/service.py`
- Test: `icore-agent/tests/unit/test_commerce_task_generation.py`

**Task Generation Rules:**

- Low stock -> replenishment task.
- Negative or low margin -> SKU cost review task.
- Supplier lead time risk -> supplier follow-up task.
- Order exception -> operations review task.

**Verification:**

- Task generation tests cover each rule.
- Tasks are idempotent for same organization/date/SKU/reason.

**Commit:**

```bash
git add icore-agent/src/icore_agent/application/commerce/task_generation.py icore-agent/src/icore_agent/application/commerce/service.py icore-agent/tests/unit/test_commerce_task_generation.py
git commit -m "Generate Commerce OS operational tasks"
```

---

## Milestone 7: Deployment Readiness for Ad Testing

**Goal:** Make the public version usable for lead capture and demos.

### Task 13: Add Free Diagnosis Flow

**Files:**

- Modify: `icore-agent-web/src/components/landing/HeroSection.vue`
- Create: `icore-agent-web/src/views/CommerceDiagnosisView.vue`
- Modify: `icore-agent-web/src/router.js`
- Modify: `icore-agent/src/icore_agent/interfaces/http/v1/account/handlers/lead.py`
- Modify: `icore-agent/src/icore_agent/interfaces/http/v1/account/schemas/lead.py`
- Test: `icore-agent/tests/test_account_flow.py`

**Behavior:**

- Landing CTA routes to `/diagnosis`.
- User can leave email and business type.
- User can upload CSV later after registration.
- Lead payload captures interest in Commerce OS.

**Verification:**

- Backend lead capture tests.
- Frontend build.

**Commit:**

```bash
git add icore-agent-web/src/components/landing/HeroSection.vue icore-agent-web/src/views/CommerceDiagnosisView.vue icore-agent-web/src/router.js icore-agent/src/icore_agent/interfaces/http/v1/account/handlers/lead.py icore-agent/src/icore_agent/interfaces/http/v1/account/schemas/lead.py icore-agent/tests/test_account_flow.py
git commit -m "Add Commerce OS diagnosis lead flow"
```

### Task 14: Final Verification

**Commands:**

```bash
cd icore-agent
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest

cd ../icore-agent-web
npm test
npm run build
```

If Go services are untouched, do not block the Commerce UI/API milestone on Go tests. If gateway routing or deployment compose files change, run relevant Go tests and Compose config checks.

**Commit:**

Only commit if verification passes and staged files are scoped to Commerce OS work.

---

## Recommended Delivery Order

For the fastest visible product, execute in this order:

1. Milestone 1: Product shell and landing page.
2. Milestone 4 with demo API mocked locally if needed.
3. Milestone 2 and 3 backend skeleton/read APIs.
4. Milestone 5 CSV import.
5. Milestone 6 Daily Brief and task generation.
6. Milestone 7 diagnosis flow.

If time is tight, the minimum public demo is:

- Commerce landing page.
- `/commerce` dashboard with demo data.
- Daily Brief panel.
- Task list.
- Data Import placeholder.
- Lead capture CTA.

This is enough to deploy and run small-budget ads while the backend import and analytics mature.

---

## Risks and Mitigations

### Risk: Building Too Much ERP

Mitigation: V1 only stores enough data for dashboard, brief, inventory risk, and supplier tasks.

### Risk: AI Output Hallucinates Business Facts

Mitigation: Facts come from deterministic analytics; LLM only explains and rewrites.

### Risk: Single-Team Pilot Blocks SaaS Later

Mitigation: Every commerce table has `organization_id` from day one.

### Risk: Public Demo Has No Data

Mitigation: Demo mode and sample data are first-class V1 features.

### Risk: CSV Import Becomes Messy

Mitigation: Provide strict templates first. Add flexible column mapping later.

---

## Acceptance Criteria

V1 is acceptable when:

- A visitor can understand the Commerce OS positioning from the landing page.
- A logged-in user can open `/commerce`.
- The dashboard shows realistic sample KPIs and risk lists.
- Daily Brief explains business status and suggested priorities.
- Tasks show suggested operational actions.
- Data Import page communicates the CSV onboarding path.
- Backend commerce data is scoped by organization.
- Tests pass for backend commerce services and frontend API/client code.

