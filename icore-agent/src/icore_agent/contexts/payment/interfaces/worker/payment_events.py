"""Kafka worker that applies payment-service success events to accounts."""

# ruff: noqa: E402,I001
# autopep8: off

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
from dataclasses import dataclass
from typing import Any

from icore_agent.config.dotenv import load_domain_dotenvs

load_domain_dotenvs()

from icore_agent.config import settings
from icore_agent.contexts.account.infrastructure.control_plane.json_store import control_plane_store
from icore_agent.contexts.payment.infrastructure.persistence.payment_events import (
    PostgresPaymentEventRepository,
)
from icore_agent.shared.logging.app_logger import get_logger
from icore_agent.shared.logging.logging_service_client import default_logging_client

# autopep8: on


_WORKER_SERVICE = "icore-payment-events-consumer"

log = get_logger(__name__, service=_WORKER_SERVICE)


@dataclass(frozen=True, slots=True)
class PaymentEventsWorkerSettings:
    """Runtime settings for the payment events Kafka consumer."""

    brokers: tuple[str, ...]
    topic: str
    group_id: str
    poll_timeout_ms: int

    @classmethod
    def from_env(cls) -> PaymentEventsWorkerSettings:
        """Load worker settings from process environment."""
        brokers = tuple(
            value.strip()
            for value in os.getenv("PAYMENT_EVENTS_KAFKA_BROKERS", "kafka:9092").split(",")
            if value.strip()
        )
        return cls(
            brokers=brokers,
            topic=os.getenv("PAYMENT_EVENTS_KAFKA_TOPIC",
                            "payment.events.v1").strip(),
            group_id=os.getenv(
                "PAYMENT_EVENTS_GROUP_ID",
                "icore-agent-payment-events",
            ).strip(),
            poll_timeout_ms=int(
                os.getenv("PAYMENT_EVENTS_POLL_TIMEOUT_MS", "1000")),
        )


async def run_worker(
    settings: PaymentEventsWorkerSettings | None = None,
    repository: PostgresPaymentEventRepository | None = None,
) -> None:
    """Consume payment success events forever and commit only handled offsets."""
    from aiokafka import AIOKafkaConsumer

    settings = settings or PaymentEventsWorkerSettings.from_env()
    if not settings.brokers:
        raise ValueError("PAYMENT_EVENTS_KAFKA_BROKERS is required")
    if not settings.topic:
        raise ValueError("PAYMENT_EVENTS_KAFKA_TOPIC is required")
    if not settings.group_id:
        raise ValueError("PAYMENT_EVENTS_GROUP_ID is required")

    repository = repository or PostgresPaymentEventRepository(
        control_plane_store)
    consumer = AIOKafkaConsumer(
        settings.topic,
        bootstrap_servers=list(settings.brokers),
        group_id=settings.group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    await consumer.start()
    log.info(
        "payment_events_consumer_started",
        topic=settings.topic,
        group_id=settings.group_id,
    )
    try:
        async for message in consumer:
            await _handle_consumer_message(
                consumer,
                message,
                repository,
                settings.poll_timeout_ms,
            )
    finally:
        await consumer.stop()
        log.info(
            "payment_events_consumer_stopped",
            topic=settings.topic,
            group_id=settings.group_id,
        )


def _handle_message(
    repository: PostgresPaymentEventRepository,
    value: bytes,
    *,
    topic: str,
    partition: int,
    offset: int,
) -> bool:
    """Apply one Kafka message and return whether its offset can be committed."""
    event_id = ""
    try:
        payload = json.loads(value.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("payment event payload must be an object")
        event_id = str(payload.get("event_id") or "").strip()
        result = repository.apply_payment_succeeded(payload)
    except Exception:
        log.exception(
            "payment_event_handling_failed",
            trace_id=event_id or None,
            topic=topic,
            partition=partition,
            offset=offset,
        )
        return False

    if result.status in {"applied", "duplicate", "ignored"}:
        log.info(
            "payment_event_handled",
            trace_id=event_id or None,
            topic=topic,
            partition=partition,
            offset=offset,
            status=result.status,
        )
        return True
    log_method = log.warning if result.status == "deferred" else log.error
    log_method(
        "payment_event_not_applied",
        trace_id=event_id or None,
        topic=topic,
        partition=partition,
        offset=offset,
        status=result.status,
        reason=result.reason,
    )
    return False


async def _handle_consumer_message(
    consumer: Any,
    message: Any,
    repository: PostgresPaymentEventRepository,
    poll_timeout_ms: int,
) -> None:
    """Handle one Kafka message and advance only when that message is durable."""
    from aiokafka import TopicPartition

    topic_partition = TopicPartition(message.topic, message.partition)
    if _handle_message(
        repository,
        message.value,
        topic=str(message.topic),
        partition=int(message.partition),
        offset=int(message.offset),
    ):
        await consumer.commit({topic_partition: message.offset + 1})
        return
    consumer.seek(topic_partition, message.offset)
    await asyncio.sleep(max(poll_timeout_ms, 1) / 1000)


async def run_worker_until_stopped() -> None:
    """Run the consumer until completion or a container termination signal."""
    loop = asyncio.get_running_loop()
    worker_task = asyncio.create_task(run_worker())
    sigterm_installed = False
    try:
        loop.add_signal_handler(signal.SIGTERM, worker_task.cancel)
        sigterm_installed = True
    except (NotImplementedError, RuntimeError, ValueError):
        pass

    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    finally:
        if sigterm_installed:
            loop.remove_signal_handler(signal.SIGTERM)


def main() -> None:
    """Run the payment events worker process."""
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(run_worker_until_stopped())
    except Exception:
        log.exception("payment_events_consumer_failed")
        raise
    finally:
        default_logging_client.close(
            timeout=settings.logging_client_drain_timeout
        )


if __name__ == "__main__":
    main()
