"""Payment service migration scaffolding checks."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PAYMENT_SERVICE = PROJECT_ROOT / "src/icore_agent/services/payment-service"


def read_text(path: Path) -> str:
    """Return repository text files as UTF-8."""
    return path.read_text(encoding="utf-8")


def test_payment_migration_client_does_not_run_postgres_server() -> None:
    """Verify the payment migrate image connects to compose Postgres only."""
    dockerfile = read_text(PAYMENT_SERVICE / "Dockerfile.migrate")

    assert "FROM migrate/migrate:v4.17.1 AS migrate" in dockerfile
    assert "FROM postgres" not in dockerfile
    assert "postgresql16-client" in dockerfile or "postgresql-client" in dockerfile
    assert 'ENTRYPOINT ["/usr/local/bin/payment-db-bootstrap"]' in dockerfile


def test_payment_bootstrap_creates_database_role_schema_and_runs_migrate() -> None:
    """Verify bootstrap owns cluster setup before service-owned migrations."""
    bootstrap = read_text(PAYMENT_SERVICE / "scripts/db-bootstrap.sh")

    assert "CREATE ROLE" in bootstrap
    assert "CREATE DATABASE" in bootstrap
    assert "CREATE SCHEMA IF NOT EXISTS" in bootstrap
    assert "REVOKE ALL ON DATABASE" in bootstrap
    assert "REVOKE ALL ON SCHEMA public" in bootstrap
    assert "-path /migrations" in bootstrap
    assert "migrate" in bootstrap
    assert "PAYMENT_DATABASE_URL" in bootstrap


def test_first_payment_migration_creates_order_event_and_outbox_tables() -> None:
    """Verify first SQL migration contains the payment source-of-truth tables."""
    up = read_text(
        PAYMENT_SERVICE / "migrations/000001_create_payment_orders.up.sql"
    )
    down = read_text(
        PAYMENT_SERVICE / "migrations/000001_create_payment_orders.down.sql"
    )

    for table in (
        "payment_orders",
        "payment_provider_transactions",
        "payment_order_events",
        "payment_outbox",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in up
        assert f"DROP TABLE IF EXISTS {table}" in down

    assert "payment_catalog_items" not in up
    assert "order_no" in up
    assert "idempotency_key" in up
    assert "merchant_order_no" in up
    assert "provider_transaction_id" in up
    assert "provider_event_id" in up
    assert "CHECK (status IN" in up
    assert "CREATE INDEX IF NOT EXISTS idx_payment_provider_transactions_reconciliation" in up
    assert "CREATE INDEX IF NOT EXISTS idx_payment_outbox_pending" in up


def test_payment_compose_and_env_are_loaded_by_compose_script() -> None:
    """Verify payment migration compose and env files are wired into compose.sh."""
    compose_script = read_text(PROJECT_ROOT / "scripts/compose.sh")
    dev_compose = read_text(
        PROJECT_ROOT / "infrastructure/docker/compose/dev/payment-service.yml"
    )
    production_compose = read_text(
        PROJECT_ROOT / "infrastructure/docker/compose/production/payment-service.yml"
    )
    env_example = read_text(PROJECT_ROOT / "dotenv/dev/.env.payment.example")

    assert "infrastructure/docker/compose/dev/payment-service.yml" in compose_script
    assert "infrastructure/docker/compose/production/payment-service.yml" in compose_script
    assert '"dotenv/$MODE/.env.payment"' in compose_script
    assert "payment-db-migrate:" in dev_compose
    assert "postgres:" in dev_compose
    assert "kafka-init:" in dev_compose
    assert "condition: service_healthy" in dev_compose
    assert "condition: service_completed_successfully" in dev_compose
    assert "payment-service/Dockerfile.migrate" in dev_compose
    assert "payment-db-migrate:" in production_compose
    assert "payment-service/Dockerfile.migrate" in production_compose
    assert "network_mode: host" in production_compose
    assert "\n  postgres:" not in production_compose
    assert "\n  kafka-init:" not in production_compose
    assert "POSTGRES_ADMIN_USER" in env_example
    assert "PAYMENT_DATABASE_URL" in env_example
    assert "PAYMENT_RECONCILIATION_POLL_INTERVAL" in env_example
    assert "PAYMENT_RECONCILIATION_BATCH_SIZE" in env_example
    assert "PAYMENT_RECONCILIATION_QUERY_TIMEOUT" in env_example


def test_python_payment_event_consumer_scaffold_is_wired() -> None:
    """Verify Python has a dedicated payment success-event consumer service."""
    dev_backend_compose = read_text(
        PROJECT_ROOT / "infrastructure/docker/compose/dev/backend.yml"
    )
    production_backend_compose = read_text(
        PROJECT_ROOT / "infrastructure/docker/compose/production/backend.yml"
    )
    pyproject = read_text(PROJECT_ROOT / "pyproject.toml")
    migration = read_text(
        PROJECT_ROOT
        / "alembic/versions/0012_create_processed_payment_events.py"
    )

    assert '"aiokafka' in pyproject
    for backend_compose in (dev_backend_compose, production_backend_compose):
        assert "payment-events-consumer:" in backend_compose
        assert "python -m icore_agent.contexts.payment.interfaces.worker.payment_events" in backend_compose
        assert "PAYMENT_EVENTS_KAFKA_BROKERS" in backend_compose
        assert "PAYMENT_EVENTS_KAFKA_TOPIC" in backend_compose
        assert "PAYMENT_EVENTS_GROUP_ID" in backend_compose
        consumer = backend_compose.split("payment-events-consumer:", 1)[1]
        assert "LOGGING_SERVICE_URL" in consumer
        assert "LOGGING_SERVICE_TOKEN" in consumer
        assert "LOGGING_SERVICE_TIMEOUT" in consumer
        assert "LOGGING_CLIENT_DRAIN_TIMEOUT" in consumer
        assert "logging-service:" in consumer
    assert "network_mode: host" in production_backend_compose
    production_consumer = production_backend_compose.split(
        "payment-events-consumer:", 1
    )[1]
    assert ".env.logging" in production_consumer
    assert "http://127.0.0.1:${LOGGING_SERVICE_HOST_PORT:-8091}" in production_consumer
    assert "payment-service:" not in dev_backend_compose.split(
        "payment-events-consumer:", 1)[1]
    assert "processed_payment_events" in migration
    assert "event_id" in migration
