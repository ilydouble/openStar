# payment-service Architecture Design

Status: draft for discussion. This document records the proposed WeChat Pay Native payment microservice design. It does not include implementation code.

## Context

The backend already keeps Go microservices under `icore-agent/src/icore_agent/services/`, with `gateway`, `logging-service`, `storage-service`, and shared helpers in `lib-go`. The new payment service should follow the same location and module style.

Current account plans live in `icore-agent/src/icore_agent/domain/account/plans.py`:

- `trial`: free, 10 tasks/month
- `pro`: USD 29/month, 200 tasks/month
- `team`: USD 99/month, 1000 tasks/month
- `premium`: USD 299/month, 5000 tasks/month
- `byok`: USD 9/month, unlimited tasks with user-owned API key

The current Python payment API is still a mock/Stripe-shaped facade under `interfaces/http/v1/payment`, and `application/billing/service.py` only updates account plans directly. The WeChat Pay integration should replace that mock checkout path with a real provider-backed order workflow. The gateway should enforce runtime JWT authentication for payment HTTP routes, while the Python backend remains responsible for issuing tokens, account entitlements, and plan/quota application.

## Source Review

Checked sources:

- Official Go SDK module `github.com/wechatpay-apiv3/wechatpay-go`, pinned in `payment-service/go.mod` at `v0.2.21`.
- SDK Native package: `services/payments/native`.
- SDK callback package: `core/notify`.
- WeChat Pay merchant docs:
  - Native product overview: `https://pay.wechatpay.cn/doc/v3/merchant/4012791874`
  - Native prepay API: `https://pay.wechatpay.cn/doc/v3/merchant/4012791877`
  - Native query by merchant order number: `https://pay.wechatpay.cn/doc/v3/merchant/4012791880`
  - Payment success callback: `https://pay.wechatpay.cn/doc/v3/merchant/4012791861`
  - WeChat Pay public key: `https://pay.wechatpay.cn/doc/v3/merchant/4012153196`
  - API v3 key: `https://pay.wechatpay.cn/doc/v3/merchant/4013053267`

Relevant SDK findings:

- Client initialization should load the merchant private key, merchant certificate serial number, WeChat Pay public key id, and WeChat Pay public key. Use `option.WithWechatPayPublicKeyAuthCipher(mchID, mchCertificateSerialNumber, mchPrivateKey, wechatpayPublicKeyID, wechatpayPublicKey)` instead of the automatic platform-certificate download mode.
- Request signing still uses the merchant private key and merchant certificate serial number. WeChat Pay response and callback signature verification should use the configured WeChat Pay public key.
- Native payment uses `native.NativeApiService{Client: client}`.
- The service supports:
  - `Prepay(ctx, native.PrepayRequest)` for `/v3/pay/transactions/native`; the response contains `code_url`.
  - `QueryOrderByOutTradeNo(ctx, native.QueryOrderByOutTradeNoRequest)`.
  - `QueryOrderById(ctx, native.QueryOrderByIdRequest)`.
  - `CloseOrder(ctx, native.CloseOrderRequest)`.
- Payment callbacks should create the notify handler with `notify.NewRSANotifyHandler(mchAPIv3Key, verifiers.NewSHA256WithRSAPubkeyVerifier(wechatpayPublicKeyID, *wechatpayPublicKey))`, then use `handler.ParseNotifyRequest(ctx, request, transaction)` to verify the WeChat Pay signature and decrypt the AES-GCM resource into `payments.Transaction`.
- The callback request body must not be consumed before `ParseNotifyRequest`.

## Goals

- Add a Go `payment-service` that owns payment orders, WeChat Pay SDK integration, callback verification, reconciliation, and payment events.
- Support WeChat Pay Native payment first: web checkout returns a `code_url`; the frontend renders the QR code.
- Route payment checkout/order HTTP APIs directly from the gateway to `payment-service`. The Python backend should not proxy normal checkout traffic.
- Keep account plan mutation in the Python account/billing domain. Payment service publishes a verified `payment.order.succeeded` event; Python applies the plan idempotently.
- Use PostgreSQL as the payment order source of truth and Kafka as the integration event bus.
- Use an isolated PostgreSQL database owned by `payment-service`, with service-local `golang-migrate` migrations under `payment-service/migrations/`.
- Keep all relational access behind repository types. HTTP handlers should only validate transport input and call application services.
- Use the existing `ApiEnvelope` shape for service responses and unwrap `data` at service-client boundaries.

## Non-Goals For Phase 1

- No JSAPI, H5, app pay, mini-program pay, refunds, invoices, profit sharing, coupons, or subscriptions.
- No direct plan mutation inside the Go service.
- No client-trusted amount. The service must calculate the amount from an internal payment catalog.
- No new message broker unless Kafka cannot satisfy a concrete production requirement.

## Service Placement

Create the service at:

```text
icore-agent/src/icore_agent/services/payment-service/
```

The SDK supports Go 1.16+, but this repository's Go workspace currently uses Go 1.22, so the new module should follow Go 1.22 to match existing services.

Proposed implementation structure:

```text
payment-service/
  cmd/payment-service/main.go
  docs/architecture-design.md
  internal/
    application/
      checkout/
      notification/
      reconciliation/
    config/
    domain/
      catalog/
      payment/
    infrastructure/
      kafka/
      persistence/postgres/
      wechatpay/
    interfaces/
      http/v1/
```

Boundary rules:

- `domain/payment`: order aggregate, status transitions, amount/currency value objects, idempotency rules.
- `domain/catalog`: payable SKU and plan-price definitions. It mirrors account plan codes but owns payment prices.
- `application/checkout`: create Native prepay order and return `code_url`.
- `application/notification`: verify callback, persist provider transaction state, and create outbox event.
- `application/reconciliation`: query WeChat Pay for pending orders and close expired orders.
- `infrastructure/wechatpay`: SDK client, Native adapter, notify handler, and provider error mapping.
- `infrastructure/persistence/postgres`: repositories and transactional outbox storage.
- `interfaces/http`: Chi routes using `github.com/go-chi/chi/v5`, request/response DTOs, trusted gateway identity headers, optional service-token auth for internal routes, and callback endpoint.
- `payment-service` HTTP code uses `net/http` plus Chi handler signatures. The shared `lib-go/http/api` package has been migrated to framework-neutral `net/http` helpers backed by Chi routing.

Shared Go HTTP helper direction:

- Shared HTTP helpers should stay Chi-compatible and expose framework-neutral helpers for ApiEnvelope responses, bounded JSON decoding, and service-token middleware.
- `logging-service`, `storage-service`, `gateway`, and `payment-service` should not introduce `github.com/gin-gonic/gin`.

## Payment Catalog

`plans.py` prices are USD-oriented product metadata. WeChat Pay charges in CNY cents. Phase 1 should introduce an explicit payment catalog for China-region WeChat Pay pricing:

- `plan_code`: `pro`, `team`, `premium`, `byok`.
- `billing_period`: initially `monthly`; later `yearly`.
- `currency`: `CNY`.
- `amount_cents`: integer amount in fen.
- `description`: short, user-visible WeChat order description.
- `entitlements_version`: version string used by Python to know which plan/quota rules apply.
- `enabled`: controls rollout without code changes.

The service must reject requests for disabled or unknown plans. It should not convert USD to CNY at runtime. The actual CNY price table is a product decision and should be configured explicitly before implementation.

## HTTP Contract

Payment browser-facing APIs should be served by `payment-service` and reached through the Go gateway. The gateway remains responsible for validating the frontend JWT, stripping spoofable identity headers, and forwarding trusted identity headers such as `X-User-ID`.

Gateway-routed payment-service endpoints:

```text
POST /api/v1/payment/native/prepay
GET  /api/v1/payment/orders/{out_trade_no}
POST /api/v1/payment/orders/{out_trade_no}/close
GET  /health
GET  /ready
```

WeChat callback endpoint:

```text
POST /webhooks/wechatpay/native
```

`prepay` request:

```json
{
  "plan_code": "pro",
  "billing_period": "monthly",
  "client_request_id": "frontend-generated-id",
  "payer_client_ip": "203.0.113.10"
}
```

`prepay` response data:

```json
{
  "order_id": "uuid",
  "out_trade_no": "wx01HZY7M6W3J9X4P0Q8M2N7K5A",
  "code_url": "weixin://wxpay/bizpayurl?...",
  "status": "pending",
  "amount": {
    "currency": "CNY",
    "total": 19900
  },
  "expires_at": "2026-05-31T12:30:00Z"
}
```

The payment-service handler derives `user_id` from the trusted `X-User-ID` header set by the gateway, not from the client JSON body. `payer_client_ip` should be derived server-side from gateway-forwarded headers when possible; if accepted from the request body during early development, it must not drive security decisions.

Gateway routing needs two changes during implementation:

- Route `/api/v1/payment/native/prepay`, `/api/v1/payment/orders/{out_trade_no}`, and `/api/v1/payment/orders/{out_trade_no}/close` to `payment-service` as JWT-protected routes.
- Route `/webhooks/wechatpay/native` directly to `payment-service` without user auth, because WeChat Pay must send the original signed body to the service that verifies it.

## Python Boundary

The current Python payment module is a mock/Stripe-shaped compatibility surface, not a real payment domain owner. It currently creates a fake checkout URL, accepts a no-op Stripe webhook, returns an empty order list, and upgrades plans directly through `BillingService`.

With an independent `payment-service`, normal payment traffic should not pass through Python:

- Checkout creation goes gateway -> `payment-service`.
- Order status reads and user-initiated closes go gateway -> `payment-service`.
- WeChat Pay callbacks go gateway -> `payment-service` with no JWT requirement.

Python remains involved only where it owns account state:

- Account registration/login and JWT issuance remain Python-owned.
- Current plan and quota reads remain Python-owned.
- Applying a verified paid order to `users.plan`, `plan_label`, BYOK flags, and quota metadata remains Python-owned through an idempotent Kafka consumer for `payment.order.succeeded`.
- Direct BYOK/offline upgrade paths remain separate from WeChat Pay checkout unless product requirements later move them into the payment service.

## Domain Model

Payment order status:

- `created`: local order created, WeChat prepay not completed.
- `pending`: prepay succeeded and QR code can be displayed.
- `paid`: verified WeChat transaction has `trade_state=SUCCESS`.
- `closed`: unpaid order closed locally and/or by WeChat.
- `expired`: local payable window expired; reconciliation should close the WeChat order.
- `failed`: provider call failed in a non-retryable way.

Core tables:

- `payment_orders`
  - `id`
  - `out_trade_no` unique, WeChat merchant order number, 6-32 allowed characters.
  - `user_public_id`
  - `plan_code`
  - `billing_period`
  - `amount_cents`
  - `currency`
  - `status`
  - `code_url`
  - `code_url_expires_at`
  - `wechat_transaction_id`
  - `wechat_trade_state`
  - `client_request_id`
  - `idempotency_key`
  - `version`
  - `created_at`, `updated_at`, `paid_at`, `closed_at`
- `payment_order_events`
  - append-only audit trail for local and provider events.
  - unique `provider_event_id` for WeChat notifications.
  - sanitized payload only; do not store secrets.
- `payment_outbox`
  - transactional event records to publish to Kafka after DB commit.
  - unique event id and publish status for retries.
- `payment_catalog_items`
  - plan-code and CNY pricing records, or use config first and migrate to table later.

Because `payment-service` owns an isolated PostgreSQL database, these tables must be introduced by service-local `golang-migrate` migrations under `payment-service/migrations/`. Alembic remains only for Python-owned database changes, such as a future processed-payment-event table used by the Python account/billing consumer.

## Idempotency

Idempotency must exist at three layers.

Client prepay idempotency:

- Python generates or forwards `client_request_id`.
- Payment service derives an `idempotency_key` from `user_id`, `plan_code`, `billing_period`, and `client_request_id`.
- If the same key is seen with the same payload and an active `pending` order exists, return the existing `code_url`.
- If the same key is seen with different amount/plan/period, return conflict.
- If an order is already `paid`, return the paid order state instead of creating another charge.

WeChat merchant order idempotency:

- `out_trade_no` is unique in PostgreSQL and unique under the WeChat merchant account.
- Generate it as a compact ASCII-safe value, for example `wx` plus ULID, staying within WeChat's 32-character limit.
- Never reuse `out_trade_no` for a changed amount or plan.

Callback idempotency:

- Store WeChat notification `id` with a unique constraint.
- Parse and verify the callback before mutating state.
- Process callback state transitions inside a DB transaction with a row lock on `payment_orders`.
- If a duplicate success notification arrives for an already-paid order, record the duplicate event and return success.
- Compare callback amount, currency, `appid`, `mchid`, `out_trade_no`, and transaction id before marking paid.

## Concurrency And Capacity

The service should be stateless at the HTTP layer and horizontally scalable.

Concurrency controls:

- Use PostgreSQL unique constraints for `out_trade_no`, `idempotency_key`, and `provider_event_id`.
- Use row-level locks or optimistic `version` checks when transitioning order state.
- Partition Kafka events by `user_public_id` for ordered entitlement application per user.
- Use short context deadlines for WeChat API calls and callback processing.
- Keep callback handlers fast: verify, persist, enqueue outbox, respond `200` or `204`; slower plan activation happens asynchronously.

Capacity defaults:

- Reuse the shared Go HTTP server timeouts.
- Configure DB pool size, max idle connections, and query deadlines explicitly.
- One reconciliation worker group per service instance using `FOR UPDATE SKIP LOCKED` or equivalent claim semantics.
- Expose queue depth, callback latency, WeChat API latency, and outbox lag metrics before increasing concurrency.

## Event-Driven Integration

Use Kafka first because it already exists in this repo and is sufficient for phase 1.

Topics:

- `payment.events.v1`: payment lifecycle events.
- Optional later: `payment.reconciliation.commands.v1` if reconciliation is split out.

Important event types:

- `payment.order.created`
- `payment.order.pending`
- `payment.order.succeeded`
- `payment.order.closed`
- `payment.order.expired`
- `payment.order.failed`

`payment.order.succeeded` payload:

```json
{
  "event_id": "uuid",
  "event_type": "payment.order.succeeded",
  "occurred_at": "2026-05-31T12:01:00Z",
  "order_id": "uuid",
  "out_trade_no": "wx01HZY7M6W3J9X4P0Q8M2N7K5A",
  "wechat_transaction_id": "420000...",
  "user_id": "uuid-public-id",
  "plan_code": "pro",
  "billing_period": "monthly",
  "amount": {
    "currency": "CNY",
    "total": 19900
  },
  "entitlements_version": "account-plans-v2"
}
```

Python account/billing should consume `payment.order.succeeded` and apply the plan in an idempotent handler keyed by `event_id` or `order_id`. That keeps payment provider logic out of the account domain and account mutation out of the payment service.

The service should use a transactional outbox, not direct publish inside the callback transaction. Direct publish can lose events if the DB commit fails after the publish or if Kafka is unavailable after a successful payment update.

## Kafka Versus RocketMQ

Recommendation: do not add RocketMQ in phase 1.

Kafka is already deployed, tested in this repo, and supports the needed event stream, replay, partition ordering, and consumer-group behavior. Payment timeout and reconciliation do not require broker-level delayed messages; they can be handled by PostgreSQL due-time queries plus a reconciliation worker.

RocketMQ becomes worth revisiting only if one of these becomes a real requirement:

- broker-native delayed messages are needed at high volume for payment timeouts;
- transactional messages are required across services and accepted operationally;
- the deployment environment already standardizes on RocketMQ for financial workflows;
- Kafka operations become a bottleneck for payment event retention or ordering needs.

Adding RocketMQ now would duplicate broker operations, observability, ACLs, dead-letter policy, and incident response for little immediate benefit.

## Reconciliation

Callbacks are not enough. The service must actively query WeChat for uncertain orders.

Reconciliation jobs:

- Query `pending` orders near or past their payable window.
- Use `QueryOrderByOutTradeNo` first because unpaid orders may not have a WeChat transaction id.
- If WeChat returns `SUCCESS`, transition to `paid` and emit `payment.order.succeeded`.
- If WeChat returns unpaid/closed states past local expiry, close or expire locally.
- Call `CloseOrder` when the local payable window has ended and the order is still unpaid.
- Retry transient WeChat/API/network failures with bounded backoff.

The job should be safe to run on multiple instances via row claiming and idempotent transitions.

## Security And Configuration

Required configuration:

- `PAYMENT_SERVICE_ADDR`
- `PAYMENT_SERVICE_TOKEN`
- `PAYMENT_DATABASE_URL`
- `PAYMENT_KAFKA_BROKERS`
- `PAYMENT_KAFKA_TOPIC`
- `PAYMENT_CATALOG_JSON_PATH`
- `WECHATPAY_APP_ID`
- `WECHATPAY_MCH_ID`
- `WECHATPAY_MCH_CERT_SERIAL_NO`
- `WECHATPAY_MCH_PRIVATE_KEY_PATH`
- `WECHATPAY_API_V3_KEY`
- `WECHATPAY_PUBLIC_KEY_ID`
- `WECHATPAY_PUBLIC_KEY_PATH`
- `WECHATPAY_NOTIFY_URL`
- `WECHATPAY_API_HOST`
- `WECHATPAY_REQUIRE_PRODUCTION_HOST`
- `PAYMENT_ORDER_TTL`

`WECHATPAY_API_HOST` is empty for the official production host. For sandbox verification, set it to the WeChat Pay sandbox API host and keep `WECHATPAY_REQUIRE_PRODUCTION_HOST=false`. Production deployments should set `WECHATPAY_REQUIRE_PRODUCTION_HOST=true` to prevent accidentally routing signed payment requests to a non-production endpoint.

Default local service-owned configuration files live under `payment-service/config/` and are mounted in compose at `/etc/icore/payment-service`:

- catalog: `/etc/icore/payment-service/catalog/plan_items.json`
- merchant private key: `/etc/icore/payment-service/wechatpay/secrets/apiclient_key.pem`
- WeChat Pay public key: `/etc/icore/payment-service/wechatpay/public/wechatpay_public_key.pem`

Secrets policy:

- Do not commit `.env` files, real private keys, certificates, or API v3 keys.
- Keep `dotenv/.env.payment.example` complete with placeholders.
- Mount the merchant private key as a read-only secret file.
- Mount the WeChat Pay public key as a pinned read-only configuration file. The public key is not a secret, but the key id and file contents must be reviewed together because they define the trust anchor for response and callback verification.
- Rotate merchant certificates by deploying a new private key path and serial number together.
- Rotate the WeChat Pay public key by deploying the new public key id and public key file together.
- Treat API v3 key rotation as a coordinated maintenance event because old keys stop working after replacement.

Callback hardening:

- Do not protect WeChat callbacks with the internal service token; WeChat cannot provide it.
- Rely on SDK public-key signature verification and AES-GCM decrypt before trusting any callback body.
- Log only sanitized identifiers and status; never log API v3 key, private key material, full Authorization header, or raw ciphertext payloads unless explicitly redacted.

## Failure Handling

Prepay failures:

- Validation failure: return 400-style envelope to Python.
- WeChat `OUT_TRADE_NO_USED`: query by `out_trade_no`; if payload matches existing order, return existing state; otherwise mark local order failed and require a new order id.
- WeChat frequency/system/network failures: retry with bounded backoff only when the request body is identical.

Callback failures:

- Signature or decrypt failure: return 4xx/5xx with failure body so WeChat can retry according to its policy.
- Verified duplicate success: return success.
- Verified success with amount or merchant mismatch: do not mark paid; persist an audit event and alert.

Outbox failures:

- Order state remains committed.
- Publisher retries pending outbox rows until Kafka accepts the event.
- Python account plan is not upgraded until the success event is consumed, so UI should show payment state separately from entitlement state for a short time.

## Python Backend Changes Needed Later

No Python changes are included in this design-only step, but implementation should later:

- Remove or stop routing frontend checkout/order calls to the current mock payment handlers once the gateway routes payment paths directly to `payment-service`.
- Keep FastAPI response envelopes unchanged for Python-owned account APIs.
- Add idempotent Kafka consumer logic to apply `payment.order.succeeded` to `users.plan`, `plan_label`, and quota metadata.
- Align existing `upgrade_plan` validation with `Plan` values (`pro`, `team`, `premium`, `byok`) instead of the current mock-era list.
- Keep direct BYOK/offline upgrade path separate from paid WeChat checkout.

## Test Strategy

Go service tests:

- Domain status transition tests.
- Catalog validation tests.
- Idempotent prepay tests for same key/same payload, same key/different payload, paid existing order, and expired order.
- Callback tests using SDK-style signed/decrypted fixtures or a provider adapter fake.
- Repository tests for unique constraints and row-lock state transitions.
- Outbox publisher tests.
- Reconciliation tests for `SUCCESS`, unpaid, closed, expired, and transient provider errors.
- HTTP route tests using Chi and `net/http/httptest`; `payment-service/go.mod` should not introduce `github.com/gin-gonic/gin`.
- Shared HTTP helper migration tests should keep existing `logging-service` and `storage-service` route behavior covered while moving the helper surface from Gin to Chi.

Python tests later:

- Payment routes are no longer handled by Python after gateway cutover.
- Kafka success-event consumer applies plan exactly once.
- Plan catalog/account plan alignment checks.

Operational verification later:

- `go test ./...` in `payment-service`.
- Existing Go workspace tests.
- Relevant Python payment/account tests.
- Docker Compose smoke test: prepay with fake provider, callback fixture, Kafka event, account plan applied.

## Open Decisions

- Final CNY price table for `pro`, `team`, `premium`, and `byok`.
- Whether yearly plans are required in phase 1.
- Whether one user can have multiple active pending orders for different plans, or whether a new checkout should close previous pending orders.
- Exact public callback URL and gateway route shape in the deployment environment.
- Whether payment-service should expose a QR image endpoint or only return `code_url`; the recommended phase 1 choice is only `code_url`.
