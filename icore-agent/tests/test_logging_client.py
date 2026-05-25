from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

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
