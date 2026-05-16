from __future__ import annotations

from datetime import UTC, datetime

from icore_agent.lib.http.request.request_context import clear_request_id, set_request_id
from icore_agent.lib.logging.contracts.v1 import LogEvent, LogLevel
from icore_agent.lib.logging.logger import Logger
from icore_agent.lib.logging.service_logger import get_service_logger


class CapturingLogger(Logger):
    """Logger double that records direct logging-service events in memory."""

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


def test_service_logger_emits_icore_backend_event_with_request_context():
    """Verify backend module logs go directly to logging-service."""
    capture = CapturingLogger()
    log = get_service_logger(
        "icore_agent.tests",
        logger=capture,
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

    assert len(capture.events) == 1
    event = capture.events[0]
    assert event.level == LogLevel.INFO
    assert event.service == "icore-backend"
    assert event.message == "tool_call"
    assert event.trace_id == "req-service-log"
    assert event.metadata["logger"] == "icore_agent.tests"
    assert event.metadata["api_key"] == "[REDACTED]"
    assert event.metadata["nested"]["token"] == "[REDACTED]"
    assert event.metadata["nested"]["safe"] == "value"


def test_service_logger_preserves_warning_level():
    """Verify warning call sites keep their logging-service severity."""
    capture = CapturingLogger()
    log = get_service_logger(
        "icore_agent.tests",
        logger=capture,
        now=lambda: datetime(2026, 5, 16, 7, 30, tzinfo=UTC),
    )

    log.warning("auth_validation_error", error="bad token")

    assert len(capture.events) == 1
    assert capture.events[0].level == LogLevel.WARNING
    assert capture.events[0].message == "auth_validation_error"
    assert capture.events[0].metadata["error"] == "bad token"
