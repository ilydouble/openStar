from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import aiokafka

from icore_agent.application.usage.policy import default_usage
from icore_agent.domain.account.plans import Plan
from icore_agent.domain.user import UserProfile
from icore_agent.infrastructure.persistence.payment_event_models import (
    ProcessedPaymentEvent,
)
from icore_agent.infrastructure.persistence.payment_events import (
    PaymentEventApplyResult,
    PostgresPaymentEventRepository,
)
from icore_agent.infrastructure.persistence.sqlalchemy.sync_session import (
    ensure_user_schema,
    sync_session_scope,
)
from icore_agent.infrastructure.persistence.users.sqlalchemy_repository import (
    SqlAlchemyUserRepository,
)
from icore_agent.workers import payment_events as payment_events_worker


class RecordingStore:
    """Capture control-plane events emitted by payment event processing."""

    def __init__(self) -> None:
        """Create an empty event recorder."""
        self.events: list[tuple[str, dict]] = []

    def append_event(self, event_type: str, **payload) -> None:
        """Record one emitted event."""
        self.events.append((event_type, payload))


def test_payment_succeeded_event_upgrades_plan_once() -> None:
    """Payment success events must apply entitlements exactly once."""
    ensure_user_schema()
    public_id = str(uuid4())
    store = RecordingStore()
    _create_user(public_id, byok={"enabled": True, "api_key": "keep-me"})

    repo = PostgresPaymentEventRepository(store)
    payload = _payment_succeeded_payload(
        event_id="evt-payment-success-1",
        user_id=public_id,
        plan_code="pro",
    )

    first = repo.apply_payment_succeeded(payload)
    second = repo.apply_payment_succeeded(payload)

    assert first.status == "applied"
    assert second.status == "duplicate"
    with sync_session_scope() as session:
        user = SqlAlchemyUserRepository(session).get_by_public_id(public_id)

    assert user is not None
    assert user.plan == Plan.PRO.value
    assert user.plan_label == Plan.PRO.limits.label
    assert user.byok == {"enabled": True, "api_key": "keep-me"}
    assert store.events == [
        (
            "payment_plan_applied",
            {
                "user_id": public_id,
                "old_plan": Plan.TRIAL.value,
                "new_plan": Plan.PRO.value,
                "event_id": "evt-payment-success-1",
                "order_id": "11111111-1111-7111-8111-111111111111",
                "order_no": "wx202606041200000000000001",
            },
        )
    ]


def test_payment_succeeded_event_rejects_unknown_plan() -> None:
    """Payment events must not write unknown plan codes into account state."""
    ensure_user_schema()
    public_id = str(uuid4())
    _create_user(public_id)

    repo = PostgresPaymentEventRepository(RecordingStore())
    payload = _payment_succeeded_payload(
        event_id="evt-payment-success-2",
        user_id=public_id,
        plan_code="enterprise",
    )

    result = repo.apply_payment_succeeded(payload)

    assert result.status == "rejected"
    assert "unsupported plan" in result.reason
    with sync_session_scope() as session:
        user = SqlAlchemyUserRepository(session).get_by_public_id(public_id)

    assert user is not None
    assert user.plan == Plan.TRIAL.value


def test_byok_payment_event_waits_for_configured_credentials() -> None:
    """BYOK payments must not activate unlimited usage before credentials exist."""
    ensure_user_schema()
    public_id = str(uuid4())
    store = RecordingStore()
    _create_user(public_id, byok={"enabled": False, "api_key": ""})

    repo = PostgresPaymentEventRepository(store)
    payload = _payment_succeeded_payload(
        event_id="evt-payment-byok-missing-credentials",
        user_id=public_id,
        plan_code="byok",
    )

    result = repo.apply_payment_succeeded(payload)

    assert result.status == "deferred"
    assert "byok credentials required" in result.reason
    with sync_session_scope() as session:
        user = SqlAlchemyUserRepository(session).get_by_public_id(public_id)
        processed = session.get(
            ProcessedPaymentEvent,
            "evt-payment-byok-missing-credentials",
        )

    assert user is not None
    assert user.plan == Plan.TRIAL.value
    assert processed is None
    assert store.events == []


def test_byok_payment_event_applies_when_credentials_are_configured() -> None:
    """BYOK payment events may activate only existing enabled BYOK credentials."""
    ensure_user_schema()
    public_id = str(uuid4())
    store = RecordingStore()
    byok = {
        "enabled": True,
        "api_key": "user-owned-key",
        "api_base": "https://llm.example.com/v1",
        "model": "openai/gpt-4.1",
    }
    _create_user(public_id, byok=byok)

    repo = PostgresPaymentEventRepository(store)
    payload = _payment_succeeded_payload(
        event_id="evt-payment-byok-configured",
        user_id=public_id,
        plan_code="byok",
    )

    result = repo.apply_payment_succeeded(payload)

    assert result.status == "applied"
    with sync_session_scope() as session:
        user = SqlAlchemyUserRepository(session).get_by_public_id(public_id)

    assert user is not None
    assert user.plan == Plan.BYOK.value
    assert user.byok == byok
    assert store.events[0][1]["new_plan"] == Plan.BYOK.value


def test_worker_consumer_starts_from_earliest_offset(monkeypatch) -> None:
    """New payment event consumer groups must backfill existing payment events."""
    created: list[FakeConsumer] = []

    def fake_consumer(*args, **kwargs):
        consumer = FakeConsumer(*args, **kwargs)
        created.append(consumer)
        return consumer

    monkeypatch.setattr(aiokafka, "AIOKafkaConsumer", fake_consumer)

    asyncio.run(
        payment_events_worker.run_worker(
            settings=payment_events_worker.PaymentEventsWorkerSettings(
                brokers=("localhost:9092",),
                topic="payments",
                group_id="payment-consumer",
                poll_timeout_ms=1,
            ),
            repository=StaticPaymentEventRepository("applied"),
        )
    )

    assert created[0].kwargs["auto_offset_reset"] == "earliest"


def test_worker_commits_only_the_handled_message_offset(monkeypatch) -> None:
    """Handled payment events must commit only their own next offset."""
    message = _kafka_message(offset=41)
    consumer = FakeConsumer(messages=[message])
    monkeypatch.setattr(aiokafka, "AIOKafkaConsumer",
                        lambda *args, **kwargs: consumer)

    asyncio.run(
        payment_events_worker.run_worker(
            settings=payment_events_worker.PaymentEventsWorkerSettings(
                brokers=("localhost:9092",),
                topic="payments",
                group_id="payment-consumer",
                poll_timeout_ms=1,
            ),
            repository=StaticPaymentEventRepository("applied"),
        )
    )

    topic_partition = aiokafka.TopicPartition("payments", 2)
    assert consumer.commits == [{topic_partition: 42}]


def test_worker_seeks_failed_message_without_committing(monkeypatch) -> None:
    """Deferred payment events must stay at their current Kafka offset."""
    message = _kafka_message(offset=7)
    consumer = FakeConsumer(messages=[message])
    monkeypatch.setattr(aiokafka, "AIOKafkaConsumer",
                        lambda *args, **kwargs: consumer)

    asyncio.run(
        payment_events_worker.run_worker(
            settings=payment_events_worker.PaymentEventsWorkerSettings(
                brokers=("localhost:9092",),
                topic="payments",
                group_id="payment-consumer",
                poll_timeout_ms=1,
            ),
            repository=StaticPaymentEventRepository("deferred"),
        )
    )

    topic_partition = aiokafka.TopicPartition("payments", 2)
    assert consumer.commits == []
    assert consumer.seeks == [(topic_partition, 7)]


class StaticPaymentEventRepository:
    """Repository fake that returns one configured apply status."""

    def __init__(self, status: str) -> None:
        """Create a repository fake with a fixed status."""
        self._status = status

    def apply_payment_succeeded(self, payload: dict) -> PaymentEventApplyResult:
        """Return the configured apply result for any payment payload."""
        del payload
        return PaymentEventApplyResult(self._status, "test reason")


class FakeConsumer:
    """Small async iterator fake for AIOKafkaConsumer."""

    def __init__(self, *topics, messages=None, **kwargs) -> None:
        """Create a fake consumer with optional queued messages."""
        del topics
        self.kwargs = kwargs
        self._messages = list(messages or [])
        self.commits: list[dict] = []
        self.seeks: list[tuple[aiokafka.TopicPartition, int]] = []
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        """Record consumer startup."""
        self.started = True

    async def stop(self) -> None:
        """Record consumer shutdown."""
        self.stopped = True

    def __aiter__(self):
        """Return this fake as an async iterator."""
        return self

    async def __anext__(self):
        """Yield queued messages, then stop the worker loop."""
        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)

    async def commit(self, offsets=None) -> None:
        """Record explicit committed offsets."""
        self.commits.append(offsets)

    def seek(self, topic_partition: aiokafka.TopicPartition, offset: int) -> None:
        """Record seek requests."""
        self.seeks.append((topic_partition, offset))


def _kafka_message(*, offset: int) -> SimpleNamespace:
    """Build a Kafka message object for worker tests."""
    return SimpleNamespace(
        topic="payments",
        partition=2,
        offset=offset,
        value=json.dumps(
            {
                "event_type": "payment.order.succeeded",
                "event_id": "evt-worker-test",
            }
        ).encode("utf-8"),
    )


def _create_user(public_id: str, byok: dict | None = None) -> None:
    """Persist a trial user for payment event tests."""
    with sync_session_scope() as session:
        SqlAlchemyUserRepository(session).save(
            UserProfile(
                public_id=public_id,
                email=f"{public_id}@example.com",
                name="Payment User",
                plan=Plan.TRIAL.value,
                plan_label=Plan.TRIAL.limits.label,
                organization_id=None,
                organization_name=None,
                roles=["owner"],
                byok=byok or {},
                usage=default_usage(),
                created_at=123,
                updated_at=123,
            )
        )


def _payment_succeeded_payload(
    *,
    event_id: str,
    user_id: str,
    plan_code: str,
) -> dict:
    """Build a minimal payment.order.succeeded payload."""
    return {
        "event_id": event_id,
        "event_type": "payment.order.succeeded",
        "occurred_at": "2026-06-13T12:00:00Z",
        "order_id": "11111111-1111-7111-8111-111111111111",
        "order_no": "wx202606041200000000000001",
        "user_id": user_id,
        "plan_code": plan_code,
        "billing_period": "monthly",
        "amount": {"currency": "CNY", "total": 19900},
        "provider": {
            "name": "wechatpay",
            "method": "native",
            "merchant_id": "mch-1",
            "merchant_order_no": "wx202606041200000000000001",
            "transaction_id": "4200000000202606130000000001",
            "trade_state": "SUCCESS",
        },
        "entitlements_version": "account-plans-v2",
    }
