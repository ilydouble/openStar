"""Tests for the payment-event Kafka worker interface."""

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import aiokafka

from icore_agent.contexts.payment.infrastructure.persistence.payment_events import (
    PaymentEventApplyResult,
)
from icore_agent.contexts.payment.interfaces.worker import (
    payment_events as payment_events_worker,
)


def test_worker_consumer_starts_from_earliest_offset(monkeypatch) -> None:
    """New payment event consumer groups must backfill existing payment events."""
    created: list[FakeConsumer] = []

    def fake_consumer(*args: Any, **kwargs: Any) -> "FakeConsumer":
        consumer = FakeConsumer(*args, **kwargs)
        created.append(consumer)
        return consumer

    monkeypatch.setattr(aiokafka, "AIOKafkaConsumer", fake_consumer)

    asyncio.run(payment_events_worker.run_worker(
        settings=payment_events_worker.PaymentEventsWorkerSettings(
            brokers=("localhost:9092",),
            topic="payments",
            group_id="payment-consumer",
            poll_timeout_ms=1,
        ),
        repository=StaticPaymentEventRepository("applied"),
    ))

    assert created[0].kwargs["auto_offset_reset"] == "earliest"


def test_worker_commits_only_the_handled_message_offset(monkeypatch) -> None:
    """Handled payment events must commit only their own next offset."""
    message = _kafka_message(offset=41)
    consumer = FakeConsumer(messages=[message])
    monkeypatch.setattr(
        aiokafka,
        "AIOKafkaConsumer",
        lambda *args, **kwargs: consumer,
    )

    asyncio.run(payment_events_worker.run_worker(
        settings=payment_events_worker.PaymentEventsWorkerSettings(
            brokers=("localhost:9092",),
            topic="payments",
            group_id="payment-consumer",
            poll_timeout_ms=1,
        ),
        repository=StaticPaymentEventRepository("applied"),
    ))

    topic_partition = aiokafka.TopicPartition("payments", 2)
    assert consumer.commits == [{topic_partition: 42}]


def test_worker_seeks_failed_message_without_committing(monkeypatch) -> None:
    """Deferred payment events must stay at their current Kafka offset."""
    message = _kafka_message(offset=7)
    consumer = FakeConsumer(messages=[message])
    monkeypatch.setattr(
        aiokafka,
        "AIOKafkaConsumer",
        lambda *args, **kwargs: consumer,
    )

    asyncio.run(payment_events_worker.run_worker(
        settings=payment_events_worker.PaymentEventsWorkerSettings(
            brokers=("localhost:9092",),
            topic="payments",
            group_id="payment-consumer",
            poll_timeout_ms=1,
        ),
        repository=StaticPaymentEventRepository("deferred"),
    ))

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

    def __init__(
        self,
        *topics: str,
        messages: list[SimpleNamespace] | None = None,
        **kwargs: Any,
    ) -> None:
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

    def __aiter__(self) -> "FakeConsumer":
        """Return this fake as an async iterator."""
        return self

    async def __anext__(self) -> SimpleNamespace:
        """Yield queued messages, then stop the worker loop."""
        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)

    async def commit(self, offsets: dict | None = None) -> None:
        """Record explicit committed offsets."""
        self.commits.append(offsets or {})

    def seek(self, topic_partition: aiokafka.TopicPartition, offset: int) -> None:
        """Record seek requests."""
        self.seeks.append((topic_partition, offset))


def _kafka_message(*, offset: int) -> SimpleNamespace:
    """Build a Kafka message object for worker tests."""
    return SimpleNamespace(
        topic="payments",
        partition=2,
        offset=offset,
        value=json.dumps({
            "event_type": "payment.order.succeeded",
            "event_id": "evt-worker-test",
        }).encode("utf-8"),
    )
