"""Kafka worker that applies payment-service success events to accounts."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Any

from icore_agent.config.dotenv import load_domain_dotenvs
from icore_agent.infrastructure.control_plane.json_store import control_plane_store
from icore_agent.infrastructure.persistence.payment_events import (
    PostgresPaymentEventRepository,
)

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PaymentEventsWorkerSettings:
    """Runtime settings for the payment events Kafka consumer."""

    brokers: tuple[str, ...]
    topic: str
    group_id: str
    poll_timeout_ms: int

    @classmethod
    def from_env(cls) -> "PaymentEventsWorkerSettings":
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


def _handle_message(repository: PostgresPaymentEventRepository, value: bytes) -> bool:
    """Apply one Kafka message and return whether its offset can be committed."""
    try:
        payload = json.loads(value.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("payment event payload must be an object")
        result = repository.apply_payment_succeeded(payload)
    except Exception:
        log.exception("payment event handling failed")
        return False

    if result.status in {"applied", "duplicate", "ignored"}:
        log.info("payment event handled status=%s", result.status)
        return True
    log.error("payment event rejected reason=%s", result.reason)
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
    if _handle_message(repository, message.value):
        await consumer.commit({topic_partition: message.offset + 1})
        return
    consumer.seek(topic_partition, message.offset)
    await asyncio.sleep(max(poll_timeout_ms, 1) / 1000)


def main() -> None:
    """Run the payment events worker process."""
    logging.basicConfig(level=logging.INFO)
    load_domain_dotenvs()
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
