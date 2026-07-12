from __future__ import annotations

from datetime import UTC, datetime

from icore_agent.shared.http.request.request_context import clear_request_id, set_request_id
from icore_agent.shared.logging.app_logger import get_logger
from icore_agent.shared.logging.contracts.v1 import LogEvent, LogLevel
from icore_agent.shared.logging.logging_service_client import LoggingServiceClient


class CapturingLoggingClient(LoggingServiceClient):
    """Logging-service client double that records events in memory."""

    def __init__(self) -> None:
        """Create a logging-service client double without network delivery."""
        super().__init__(
            base_url="http://logging-service:8091",
            token="token",
            timeout=1.0,
        )
        self.events: list[LogEvent] = []

    def _enqueue_event(self, event: LogEvent) -> bool:
        """Capture emitted events without starting the HTTP delivery worker."""
        self.events.append(event)
        return True


def test_app_logger_emits_icore_backend_event_with_request_context():
    """Verify backend module logs go directly to logging-service."""
    client = CapturingLoggingClient()
    log = get_logger(
        "icore_agent.tests",
        client=client,
        now=lambda: datetime(2026, 5, 16, 7, 30, tzinfo=UTC),
    )
    token = set_request_id("req-service-log")
    try:
        log.info(
            "tool_call",
            api_key="secret-key",
            nested={"token": "secret-token", "safe": "value"},
        )
    finally:
        clear_request_id(token)

    assert len(client.events) == 1
    event = client.events[0]
    assert event.level == LogLevel.INFO
    assert event.service == "icore-backend"
    assert event.message == "tool_call"
    assert event.trace_id == "req-service-log"
    assert event.metadata["logger"] == "icore_agent.tests"
    assert event.metadata["api_key"] == "[REDACTED]"
    assert event.metadata["nested"]["token"] == "[REDACTED]"
    assert event.metadata["nested"]["safe"] == "value"


def test_app_logger_preserves_warning_level():
    """Verify warning call sites keep their logging-service severity."""
    client = CapturingLoggingClient()
    log = get_logger(
        "icore_agent.tests",
        client=client,
        now=lambda: datetime(2026, 5, 16, 7, 30, tzinfo=UTC),
    )

    log.warning("auth_validation_error", error="bad token")

    assert len(client.events) == 1
    assert client.events[0].level == LogLevel.WARNING
    assert client.events[0].message == "auth_validation_error"
    assert client.events[0].metadata["error"] == "bad token"


def test_app_logger_uses_explicit_service_and_trace_id() -> None:
    """Worker loggers must be able to identify their process and source event."""
    client = CapturingLoggingClient()
    log = get_logger(
        "icore_agent.worker",
        client=client,
        service="icore-payment-events-consumer",
    )

    log.info("payment_event_handled", trace_id="evt-1", status="applied")

    event = client.events[0]
    assert event.service == "icore-payment-events-consumer"
    assert event.trace_id == "evt-1"
    assert event.metadata["status"] == "applied"


def test_app_logger_exception_captures_active_exception() -> None:
    """Structured exception logs must preserve error type, text, and traceback."""
    client = CapturingLoggingClient()
    log = get_logger("icore_agent.worker", client=client)

    try:
        raise ValueError("invalid payment event")
    except ValueError:
        log.exception("payment_event_handling_failed")

    event = client.events[0]
    assert event.level == LogLevel.ERROR
    assert event.metadata["error_type"] == "ValueError"
    assert event.metadata["error"] == "invalid payment event"
    assert "ValueError: invalid payment event" in event.metadata["traceback"]
