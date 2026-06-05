CREATE TABLE IF NOT EXISTS payment_orders (
  id UUID PRIMARY KEY,
  order_no VARCHAR(32) NOT NULL,
  user_public_id VARCHAR(64) NOT NULL,
  plan_code VARCHAR(32) NOT NULL,
  billing_period VARCHAR(16) NOT NULL,
  amount_cents BIGINT NOT NULL,
  currency CHAR(3) NOT NULL,
  status VARCHAR(16) NOT NULL,
  client_request_id VARCHAR(128) NOT NULL,
  idempotency_key VARCHAR(256) NOT NULL,
  version BIGINT NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  paid_at TIMESTAMPTZ,
  closed_at TIMESTAMPTZ,
  CONSTRAINT uq_payment_orders_order_no UNIQUE (order_no),
  CONSTRAINT uq_payment_orders_idempotency_key UNIQUE (idempotency_key),
  CONSTRAINT ck_payment_orders_order_no_length CHECK (
    char_length(order_no) BETWEEN 6 AND 32
  ),
  CONSTRAINT ck_payment_orders_amount_positive CHECK (amount_cents > 0),
  CONSTRAINT ck_payment_orders_currency_upper CHECK (currency = upper(currency)),
  CONSTRAINT ck_payment_orders_status CHECK (status IN (
    'created',
    'pending',
    'paid',
    'closed',
    'expired',
    'failed'
  )),
  CONSTRAINT ck_payment_orders_version_positive CHECK (version > 0)
);

CREATE INDEX IF NOT EXISTS idx_payment_orders_user_created_at
  ON payment_orders (user_public_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_payment_orders_reconciliation
  ON payment_orders (status, created_at)
  WHERE status IN ('created', 'pending');

CREATE TABLE IF NOT EXISTS payment_provider_transactions (
  id UUID PRIMARY KEY,
  order_id UUID NOT NULL REFERENCES payment_orders(id) ON DELETE CASCADE,
  provider VARCHAR(32) NOT NULL,
  payment_method VARCHAR(32) NOT NULL,
  merchant_id VARCHAR(64) NOT NULL,
  merchant_order_no VARCHAR(64) NOT NULL,
  provider_transaction_id VARCHAR(128),
  provider_trade_state VARCHAR(64),
  status VARCHAR(16) NOT NULL,
  payment_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  paid_at TIMESTAMPTZ,
  closed_at TIMESTAMPTZ,
  CONSTRAINT ck_payment_provider_transactions_status CHECK (status IN (
    'created',
    'pending',
    'paid',
    'closed',
    'expired',
    'failed'
  )),
  CONSTRAINT ck_payment_provider_transactions_payload_object CHECK (
    jsonb_typeof(payment_payload) = 'object'
  ),
  CONSTRAINT uq_payment_provider_transactions_merchant_order UNIQUE (
    provider,
    merchant_id,
    merchant_order_no
  )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_payment_provider_transactions_provider_transaction
  ON payment_provider_transactions (provider, merchant_id, provider_transaction_id)
  WHERE provider_transaction_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_payment_provider_transactions_order_created_at
  ON payment_provider_transactions (order_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_payment_provider_transactions_reconciliation
  ON payment_provider_transactions (status, expires_at, created_at)
  WHERE status IN ('created', 'pending');

CREATE TABLE IF NOT EXISTS payment_order_events (
  id UUID PRIMARY KEY,
  order_id UUID REFERENCES payment_orders(id) ON DELETE SET NULL,
  payment_provider_transaction_id UUID REFERENCES payment_provider_transactions(id) ON DELETE SET NULL,
  event_type VARCHAR(64) NOT NULL,
  local_status VARCHAR(16),
  provider VARCHAR(32) NOT NULL,
  merchant_id VARCHAR(64) NOT NULL,
  merchant_order_no VARCHAR(64),
  provider_event_id VARCHAR(128),
  provider_transaction_id VARCHAR(128),
  provider_trade_state VARCHAR(64),
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_payment_order_events_local_status CHECK (
    local_status IS NULL OR local_status IN (
      'created',
      'pending',
      'paid',
      'closed',
      'expired',
      'failed'
    )
  ),
  CONSTRAINT ck_payment_order_events_payload_object CHECK (
    jsonb_typeof(payload) = 'object'
  )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_payment_order_events_provider_event_id
  ON payment_order_events (provider, merchant_id, provider_event_id)
  WHERE provider_event_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_payment_order_events_order_created_at
  ON payment_order_events (order_id, created_at);

CREATE TABLE IF NOT EXISTS payment_outbox (
  id UUID PRIMARY KEY,
  aggregate_type VARCHAR(64) NOT NULL,
  aggregate_id UUID NOT NULL,
  event_type VARCHAR(128) NOT NULL,
  partition_key VARCHAR(128) NOT NULL,
  payload JSONB NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  published_at TIMESTAMPTZ,
  last_error TEXT,
  CONSTRAINT ck_payment_outbox_status CHECK (status IN (
    'pending',
    'publishing',
    'published',
    'failed'
  )),
  CONSTRAINT ck_payment_outbox_attempts_nonnegative CHECK (attempts >= 0)
);

CREATE INDEX IF NOT EXISTS idx_payment_outbox_pending
  ON payment_outbox (next_attempt_at, created_at)
  WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_payment_outbox_aggregate
  ON payment_outbox (aggregate_type, aggregate_id, created_at);
