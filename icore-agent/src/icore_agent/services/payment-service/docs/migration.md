# payment-service Database Migration Plan

Status: draft for the future implementation. This document describes how `payment-service` should own its PostgreSQL schema with `golang-migrate`.

## Existing Pattern

`infrastructure/clickhouse` uses a one-shot migration container:

- `Dockerfile.migrate` copies the `migrate` binary from `migrate/migrate:v4.17.1`.
- `bootstrap.sh` waits for ClickHouse, creates the target database if needed, then runs `migrate up`.
- `infrastructure/docker/compose/click-house.yml` starts `clickhouse-migrate` after ClickHouse is healthy.
- `clickhouse-writer` starts only after `clickhouse-migrate` completes successfully.

`payment-service` should use the same operational shape: a health-gated one-shot migration service that must finish before the app container starts.

## Target Ownership Model

The payment database must be isolated from the Python backend database:

- Role: `icore_payment`
- Database: `icore_payment_db`
- Owner: `icore_payment`
- App-level invariant: only `icore_payment` should have modification privileges on `icore_payment_db`.
- Other application roles, including `icore_agent`, must not be granted privileges on `icore_payment_db`.

Strict enforcement requires that regular application roles are not PostgreSQL superusers. The current local compose defaults create `POSTGRES_USER=${DB_USER:-icore_agent}`, and the official Postgres image makes that role the initial superuser. To strictly satisfy "only `icore_payment` can modify `icore_payment_db`", local and production bootstrap should use a separate admin role, then create both `icore_agent` and `icore_payment` as non-superuser application roles.

Recommended cluster bootstrap roles:

- `icore_postgres_admin`: cluster/bootstrap admin, not used by application runtime.
- `icore_agent`: non-superuser owner of `icore_agent_db`.
- `icore_payment`: non-superuser owner of `icore_payment_db`.

## Two-Phase Migration Flow

Use two separate stages so permissions are explicit.

### Phase 1: Bootstrap Role And Database

The bootstrap phase connects as the PostgreSQL admin role and performs only cluster-level setup:

```sql
CREATE ROLE icore_payment
  LOGIN
  PASSWORD '<payment-password>'
  NOSUPERUSER
  NOCREATEDB
  NOCREATEROLE
  NOINHERIT;

CREATE DATABASE icore_payment_db
  OWNER icore_payment
  TEMPLATE template0
  ENCODING 'UTF8';
```

The real script must be idempotent because `CREATE ROLE IF NOT EXISTS` is not available in PostgreSQL. Use a guarded `DO` block for the role and `SELECT ... \gexec` for the database.

After database creation:

```sql
REVOKE ALL ON DATABASE icore_payment_db FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE icore_payment_db TO icore_payment;
```

Then connect to `icore_payment_db` and lock down schema privileges:

```sql
REVOKE ALL ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA IF NOT EXISTS payment AUTHORIZATION icore_payment;
ALTER DATABASE icore_payment_db SET search_path TO payment, public;
```

Do not grant `icore_agent` any privilege on `icore_payment_db`.

### Phase 2: Run Service-Owned Migrations

The migration phase connects as `icore_payment` and runs `golang-migrate`:

```text
migrate \
  -path /migrations \
  -database "postgres://icore_payment:${PAYMENT_DB_PASSWORD}@postgres:5432/icore_payment_db?sslmode=disable&search_path=payment" \
  up
```

Running migrations as `icore_payment` is deliberate. It proves that all payment schema changes can be applied by the payment service owner and not by the Python backend owner.

## Proposed Directory Layout

```text
icore-agent/src/icore_agent/services/payment-service/
  Dockerfile.migrate
  migrations/
    000001_create_payment_orders.up.sql
    000001_create_payment_orders.down.sql
  scripts/
    db-bootstrap.sh
```

The migration container can follow the ClickHouse image pattern:

```dockerfile
FROM migrate/migrate:v4.17.1 AS migrate

FROM postgres:16-alpine

COPY --from=migrate /usr/local/bin/migrate /usr/local/bin/migrate
COPY payment-service/scripts/db-bootstrap.sh /usr/local/bin/payment-db-bootstrap
COPY payment-service/migrations /migrations
RUN chmod +x /usr/local/bin/payment-db-bootstrap

ENTRYPOINT ["/usr/local/bin/payment-db-bootstrap"]
```

The final implementation can split the bootstrap and migration entrypoints if that makes compose dependencies clearer. The important boundary is that cluster setup uses the admin connection and schema migrations use the `icore_payment` connection.

## Compose Shape

Add a payment migration service alongside the future payment app service:

```yaml
services:
  payment-db-migrate:
    build:
      context: ../../../src/icore_agent/services
      dockerfile: payment-service/Dockerfile.migrate
    image: icore-payment-service-migrate:dev
    container_name: icore-payment-db-migrate
    restart: "no"
    environment:
      POSTGRES_ADMIN_USER: ${POSTGRES_ADMIN_USER:-icore_postgres_admin}
      POSTGRES_ADMIN_PASSWORD: ${POSTGRES_ADMIN_PASSWORD:-change-me}
      POSTGRES_HOST: ${DB_HOST:-postgres}
      POSTGRES_PORT: ${DB_INTERNAL_PORT:-5432}
      PAYMENT_DB_USER: ${PAYMENT_DB_USER:-icore_payment}
      PAYMENT_DB_PASSWORD: ${PAYMENT_DB_PASSWORD:-change-me}
      PAYMENT_DB_NAME: ${PAYMENT_DB_NAME:-icore_payment_db}
      PAYMENT_DB_SCHEMA: ${PAYMENT_DB_SCHEMA:-payment}
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - icore-net

  payment-service:
    depends_on:
      payment-db-migrate:
        condition: service_completed_successfully
```

If local development keeps the current `DB_USER=icore_agent` superuser temporarily, use the admin variables to point at that role only as a transitional development shortcut. Production should not do that.

## Environment Files

Add a payment-specific env example before implementation:

```text
dotenv/.env.payment.example
```

Expected database settings:

```text
PAYMENT_DB_HOST=postgres
PAYMENT_DB_PORT=5432
PAYMENT_DB_USER=icore_payment
PAYMENT_DB_PASSWORD=<replace-with-payment-db-password>
PAYMENT_DB_NAME=icore_payment_db
PAYMENT_DB_SCHEMA=payment
PAYMENT_DATABASE_URL=postgres://icore_payment:<replace-with-payment-db-password>@postgres:5432/icore_payment_db?sslmode=disable&search_path=payment
```

`icore-agent/scripts/compose.sh` should load `dotenv/.env.payment` when payment-service compose support is added.

## Migration Rules

- Keep payment table migrations in `payment-service/migrations/`.
- Use paired `.up.sql` and `.down.sql` files.
- Do not put payment-service tables in `icore-agent/alembic/`; Alembic remains for the Python-owned database.
- Do not let HTTP handlers issue schema changes or ad hoc SQL.
- Keep table access behind payment-service repository types.
- Avoid cross-database joins between `icore_agent_db` and `icore_payment_db`.
- Use Kafka events and internal service APIs for cross-domain coordination.

## First Migration Scope

The first migration should create the payment source-of-truth tables:

- `payment_orders`
- `payment_order_events`
- `payment_outbox`
- optionally `payment_catalog_items` if pricing is stored in the database instead of config

Use database constraints for critical invariants:

- unique `out_trade_no`
- unique `idempotency_key`
- unique provider notification/event id
- enum/check constraints for local payment status
- indexes for pending-order reconciliation and outbox publishing

## Verification

Before handing off an implementation change:

- Run `payment-db-migrate` against a fresh local volume.
- Run it a second time to prove idempotent bootstrap plus no-op migrations.
- Connect as `icore_payment` and verify it can create/alter payment tables.
- Connect as `icore_agent` and verify it cannot modify `icore_payment_db`.
- Run payment-service repository tests against `icore_payment_db`.
- Run `git diff --check`.
