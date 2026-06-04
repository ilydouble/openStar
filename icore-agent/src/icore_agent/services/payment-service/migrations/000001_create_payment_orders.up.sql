CREATE TABLE IF NOT EXISTS payment_orders (
  id UUID PRIMARY KEY,
  out_trade_no VARCHAR(32) NOT NULL,
  user_public_id VARCHAR(64) NOT NULL,
  plan_code VARCHAR(32) NOT NULL,
  billing_period VARCHAR(16) NOT NULL,
  amount_cents BIGINT NOT NULL,
  currency CHAR(3) NOT NULL,
  status VARCHAR(16) NOT NULL,
  code_url TEXT,
  code_url_expires_at TIMESTAMPTZ,
  wechat_transaction_id VARCHAR(64),
  wechat_trade_state VARCHAR(32),
  client_request_id VARCHAR(128) NOT NULL,
  idempotency_key VARCHAR(256) NOT NULL,
  version BIGINT NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  paid_at TIMESTAMPTZ,
  closed_at TIMESTAMPTZ,
  CONSTRAINT uq_payment_orders_out_trade_no UNIQUE (out_trade_no),
  CONSTRAINT uq_payment_orders_idempotency_key UNIQUE (idempotency_key),
  CONSTRAINT ck_payment_orders_out_trade_no_length CHECK (
    char_length(out_trade_no) BETWEEN 6 AND 32
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

CREATE UNIQUE INDEX IF NOT EXISTS uq_payment_orders_wechat_transaction_id
  ON payment_orders (wechat_transaction_id)
  WHERE wechat_transaction_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_payment_orders_user_created_at
  ON payment_orders (user_public_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_payment_orders_reconciliation
  ON payment_orders (status, code_url_expires_at, created_at)
  WHERE status IN ('created', 'pending');

CREATE TABLE IF NOT EXISTS payment_order_events (
  id UUID PRIMARY KEY,
  order_id UUID REFERENCES payment_orders(id) ON DELETE SET NULL,
  event_type VARCHAR(64) NOT NULL,
  local_status VARCHAR(16),
  provider VARCHAR(32) NOT NULL,
  provider_event_id VARCHAR(128),
  provider_trade_state VARCHAR(32),
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
  )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_payment_order_events_provider_event_id
  ON payment_order_events (provider, provider_event_id)
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
