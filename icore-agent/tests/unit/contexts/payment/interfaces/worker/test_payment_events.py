"""Tests for the payment-event Kafka worker interface."""

import asyncio
import json
import sys
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import aiokafka
import pytest

from icore_agent.contexts.payment.infrastructure.persistence.payment_events import (
    PaymentEventApplyResult,
)
from icore_agent.contexts.payment.interfaces.worker import (
    payment_events as payment_events_worker,
)


def test_worker_consumer_starts_from_earliest_offset(
    monkeypatch, worker_log: "RecordingLogger"
) -> None:
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
    assert worker_log.messages() == [
        "payment_events_consumer_started",
        "payment_events_consumer_stopped",
    ]


def test_worker_commits_only_the_handled_message_offset(
    monkeypatch, worker_log: "RecordingLogger"
) -> None:
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
    handled = worker_log.event("payment_event_handled")
    assert handled.level == "info"
    assert handled.metadata == {
        "trace_id": "evt-worker-test",
        "topic": "payments",
        "partition": 2,
        "offset": 41,
        "status": "applied",
    }


def test_worker_seeks_failed_message_without_committing(
    monkeypatch, worker_log: "RecordingLogger"
) -> None:
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
    deferred = worker_log.event("payment_event_not_applied")
    assert deferred.level == "warning"
    assert deferred.metadata["status"] == "deferred"
    assert deferred.metadata["reason"] == "test reason"


def test_worker_logs_rejected_events_as_errors(
    monkeypatch, worker_log: "RecordingLogger"
) -> None:
    """Rejected payment events must be observable as structured errors."""
    message = _kafka_message(offset=9)
    consumer = FakeConsumer(messages=[message])
    monkeypatch.setattr(
        aiokafka,
        "AIOKafkaConsumer",
        lambda *args, **kwargs: consumer,
    )

    asyncio.run(payment_events_worker.run_worker(
        settings=_worker_settings(),
        repository=StaticPaymentEventRepository("rejected"),
    ))

    rejected = worker_log.event("payment_event_not_applied")
    assert rejected.level == "error"
    assert rejected.metadata["trace_id"] == "evt-worker-test"
    assert rejected.metadata["offset"] == 9
    assert consumer.commits == []


def test_worker_logs_handler_exceptions_without_committing(
    monkeypatch, worker_log: "RecordingLogger"
) -> None:
    """Repository failures must retain Kafka coordinates and leave the offset pending."""
    message = _kafka_message(offset=11)
    consumer = FakeConsumer(messages=[message])
    monkeypatch.setattr(
        aiokafka,
        "AIOKafkaConsumer",
        lambda *args, **kwargs: consumer,
    )

    asyncio.run(payment_events_worker.run_worker(
        settings=_worker_settings(),
        repository=FailingPaymentEventRepository(),
    ))

    failed = worker_log.event("payment_event_handling_failed")
    assert failed.level == "exception"
    assert failed.metadata["trace_id"] == "evt-worker-test"
    assert failed.metadata["topic"] == "payments"
    assert failed.metadata["partition"] == 2
    assert failed.metadata["offset"] == 11
    assert failed.metadata["error_type"] == "RuntimeError"
    assert consumer.commits == []


def test_worker_cancellation_stops_consumer(
    monkeypatch, worker_log: "RecordingLogger"
) -> None:
    """Container cancellation must stop Kafka before the process drains logs."""
    consumer = BlockingConsumer()
    monkeypatch.setattr(
        aiokafka,
        "AIOKafkaConsumer",
        lambda *args, **kwargs: consumer,
    )

    async def cancel_worker() -> None:
        """Cancel the worker after its consumer starts waiting for messages."""
        task = asyncio.create_task(payment_events_worker.run_worker(
            settings=_worker_settings(),
            repository=StaticPaymentEventRepository("applied"),
        ))
        await consumer.iterating.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel_worker())

    assert consumer.stopped
    assert worker_log.messages() == [
        "payment_events_consumer_started",
        "payment_events_consumer_stopped",
    ]


def test_worker_main_drains_logging_client(monkeypatch) -> None:
    """The process entry point must close its logging client after asyncio exits."""
    client = RecordingCloseClient()

    async def completed_worker() -> None:
        """Represent a worker that completed without an operating system signal."""

    monkeypatch.setattr(
        payment_events_worker,
        "run_worker_until_stopped",
        completed_worker,
    )
    monkeypatch.setattr(payment_events_worker,
                        "default_logging_client", client)
    monkeypatch.setattr(
        payment_events_worker.settings,
        "logging_client_drain_timeout",
        5.0,
    )

    payment_events_worker.main()

    assert client.close_timeouts == [5.0]


@pytest.fixture
def worker_log(monkeypatch) -> "RecordingLogger":
    """Replace the process logger with a structured in-memory recorder."""
    recorder = RecordingLogger()
    monkeypatch.setattr(payment_events_worker, "log", recorder)
    return recorder


@dataclass(frozen=True, slots=True)
class RecordedLog:
    """One structured worker log captured by a test double."""

    level: str
    message: str
    metadata: dict[str, Any]


class RecordingLogger:
    """Small AppLogger-compatible recorder for worker behavior tests."""

    def __init__(self) -> None:
        """Create an empty event recorder."""
        self.events: list[RecordedLog] = []

    def info(self, message: str, **metadata: Any) -> bool:
        """Record an informational event."""
        return self._record("info", message, metadata)

    def warning(self, message: str, **metadata: Any) -> bool:
        """Record a warning event."""
        return self._record("warning", message, metadata)

    def error(self, message: str, **metadata: Any) -> bool:
        """Record an error event."""
        return self._record("error", message, metadata)

    def exception(self, message: str, **metadata: Any) -> bool:
        """Record an exception event with the active error type."""
        exc_type = sys.exc_info()[0]
        if exc_type is not None:
            metadata["error_type"] = exc_type.__name__
        return self._record("exception", message, metadata)

    def messages(self) -> list[str]:
        """Return captured message names in emission order."""
        return [event.message for event in self.events]

    def event(self, message: str) -> RecordedLog:
        """Return the single event with the requested message name."""
        matches = [event for event in self.events if event.message == message]
        assert len(matches) == 1
        return matches[0]

    def _record(self, level: str, message: str, metadata: dict[str, Any]) -> bool:
        """Append one immutable event snapshot."""
        self.events.append(RecordedLog(level, message, dict(metadata)))
        return True


class RecordingCloseClient:
    """Logging client double that records synchronous worker shutdown."""

    def __init__(self) -> None:
        """Create an empty close-call recorder."""
        self.close_timeouts: list[float | None] = []

    def close(self, *, timeout: float | None = None) -> bool:
        """Record the worker drain timeout."""
        self.close_timeouts.append(timeout)
        return True


class FailingPaymentEventRepository:
    """Repository fake that raises while applying an event."""

    def apply_payment_succeeded(self, payload: dict) -> PaymentEventApplyResult:
        """Raise a deterministic persistence failure."""
        del payload
        raise RuntimeError("database unavailable")


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


class BlockingConsumer(FakeConsumer):
    """Consumer fake that waits until its worker task is cancelled."""

    def __init__(self) -> None:
        """Create a consumer with an observable iteration wait."""
        super().__init__()
        self.iterating = asyncio.Event()

    async def __anext__(self) -> SimpleNamespace:
        """Wait forever so cancellation exercises the worker finally block."""
        self.iterating.set()
        await asyncio.Event().wait()
        raise StopAsyncIteration


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


def _worker_settings() -> payment_events_worker.PaymentEventsWorkerSettings:
    """Build the common worker settings used by behavior tests."""
    return payment_events_worker.PaymentEventsWorkerSettings(
        brokers=("localhost:9092",),
        topic="payments",
        group_id="payment-consumer",
        poll_timeout_ms=1,
    )
