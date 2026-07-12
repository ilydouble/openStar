from __future__ import annotations

import asyncio
import json
import threading
from datetime import UTC, datetime
from uuid import UUID

import httpx

from icore_agent.shared.http.request.request_context import clear_request_id, set_request_id
from icore_agent.shared.logging.contracts.v1 import LogEvent, LogLevel
from icore_agent.shared.logging.logging_service_client import LoggingServiceClient


class CapturingLoggingClient(LoggingServiceClient):
    """Logging-service client double that records events in memory."""

    def __init__(self) -> None:
        super().__init__(
            base_url="http://logging-service:8091",
            token="token",
            timeout=1.0,
        )
        self.events: list[LogEvent] = []

    def _enqueue_event(self, event: LogEvent) -> bool:
        self.events.append(event)
        return True


def test_logging_client_explicit_trace_id_wins_over_request_context():
    """Verify an explicit trace id is not overwritten by request context."""
    client = CapturingLoggingClient()
    token = set_request_id("context-id")
    try:
        client.emit_event(
            LogLevel.INFO,
            message="created",
            service="icore-agent",
            trace_id="explicit-id",
            timestamp=datetime(2026, 5, 14, tzinfo=UTC),
        )
    finally:
        clear_request_id(token)

    assert client.events[0].trace_id == "explicit-id"


def test_logging_client_explicit_empty_trace_id_wins_over_request_context():
    """Verify callers can intentionally emit an empty trace id."""
    client = CapturingLoggingClient()
    token = set_request_id("context-id")
    try:
        client.emit_event(
            LogLevel.INFO,
            message="created",
            service="icore-agent",
            trace_id="",
            timestamp=datetime(2026, 5, 14, tzinfo=UTC),
        )
    finally:
        clear_request_id(token)

    assert client.events[0].trace_id == ""


def test_logging_client_uses_request_context_when_trace_id_is_not_explicit():
    """Verify request context fills trace id when callers omit it."""
    client = CapturingLoggingClient()
    token = set_request_id("context-id")
    try:
        client.emit_event(
            LogLevel.INFO,
            message="created",
            service="icore-agent",
            timestamp=datetime(2026, 5, 14, tzinfo=UTC),
        )
    finally:
        clear_request_id(token)

    assert client.events[0].trace_id == "context-id"


def test_logging_client_allows_empty_trace_id_outside_http_request():
    """Verify background tasks can emit events without request context."""
    client = CapturingLoggingClient()

    client.emit_event(
        LogLevel.INFO,
        message="background task",
        service="icore-agent",
        timestamp=datetime(2026, 5, 14, tzinfo=UTC),
    )

    assert client.events[0].trace_id == ""


def test_logging_client_assigns_event_id_to_each_event():
    """Verify every event has a stable id before it leaves the backend process."""
    client = CapturingLoggingClient()

    client.emit_event(
        LogLevel.INFO,
        message="background task",
        service="icore-agent",
        timestamp=datetime(2026, 5, 14, tzinfo=UTC),
    )

    assert UUID(client.events[0].event_id)


def test_logging_client_close_drains_events_and_rejects_new_emits() -> None:
    """Closing must deliver queued events before rejecting subsequent logs."""
    delivered: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        """Capture one logging-service request."""
        payload = json.loads(request.content)
        delivered.append(payload["event"]["message"])
        return httpx.Response(200, json={"code": 200})

    client = LoggingServiceClient(
        base_url="http://logging-service:8091",
        token="token",
        timeout=1.0,
        sync_transport=httpx.MockTransport(handle),
    )
    assert client.emit_event(
        LogLevel.INFO,
        message="first",
        service="icore-agent",
    )
    assert client.emit_event(
        LogLevel.INFO,
        message="second",
        service="icore-agent",
    )

    assert client.close(timeout=1.0)
    assert delivered == ["first", "second"]
    assert not client.emit_event(
        LogLevel.INFO,
        message="after-close",
        service="icore-agent",
    )
    assert client.close(timeout=1.0)


def test_logging_client_close_times_out_without_waiting_forever() -> None:
    """A blocked delivery must not make process shutdown wait indefinitely."""
    delivery_started = threading.Event()
    release_delivery = threading.Event()

    def handle(_: httpx.Request) -> httpx.Response:
        """Hold one request until the test releases the worker."""
        delivery_started.set()
        release_delivery.wait(timeout=1.0)
        return httpx.Response(200, json={"code": 200})

    client = LoggingServiceClient(
        base_url="http://logging-service:8091",
        token="token",
        timeout=1.0,
        sync_transport=httpx.MockTransport(handle),
    )
    assert client.emit_event(
        LogLevel.INFO,
        message="blocked",
        service="icore-agent",
    )
    assert delivery_started.wait(timeout=1.0)

    assert not client.close(timeout=0.01)
    release_delivery.set()
    assert client.close(timeout=1.0)


def test_logging_client_aclose_drains_from_async_code() -> None:
    """The async close facade must drain events through a worker thread."""
    delivered = threading.Event()

    def handle(_: httpx.Request) -> httpx.Response:
        """Record delivery through the reusable sync transport."""
        delivered.set()
        return httpx.Response(200, json={"code": 200})

    client = LoggingServiceClient(
        base_url="http://logging-service:8091",
        token="token",
        timeout=1.0,
        sync_transport=httpx.MockTransport(handle),
    )
    assert client.emit_event(
        LogLevel.INFO,
        message="async-close",
        service="icore-agent",
    )

    assert asyncio.run(client.aclose(timeout=1.0))
    assert delivered.is_set()
