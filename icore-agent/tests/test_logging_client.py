from __future__ import annotations

from datetime import UTC, datetime

from icore_agent.lib.http.request_context import clear_request_id, set_request_id
from icore_agent.lib.logging.contracts.v1 import LogEvent, LogLevel
from icore_agent.lib.logging.logger import Logger


class CapturingLogger(Logger):
    """Logger variant that records events without starting the HTTP worker."""

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


def test_logger_explicit_trace_id_wins_over_request_context():
    logger = CapturingLogger()
    token = set_request_id("context-id")
    try:
        logger.emit_event(
            LogLevel.INFO,
            message="created",
            service="icore-agent",
            trace_id="explicit-id",
            timestamp=datetime(2026, 5, 14, tzinfo=UTC),
        )
    finally:
        clear_request_id(token)

    assert logger.events[0].trace_id == "explicit-id"


def test_logger_explicit_empty_trace_id_wins_over_request_context():
    logger = CapturingLogger()
    token = set_request_id("context-id")
    try:
        logger.emit_event(
            LogLevel.INFO,
            message="created",
            service="icore-agent",
            trace_id="",
            timestamp=datetime(2026, 5, 14, tzinfo=UTC),
        )
    finally:
        clear_request_id(token)

    assert logger.events[0].trace_id == ""


def test_logger_uses_request_context_when_trace_id_is_not_explicit():
    logger = CapturingLogger()
    token = set_request_id("context-id")
    try:
        logger.emit_event(
            LogLevel.INFO,
            message="created",
            service="icore-agent",
            timestamp=datetime(2026, 5, 14, tzinfo=UTC),
        )
    finally:
        clear_request_id(token)

    assert logger.events[0].trace_id == "context-id"


def test_logger_allows_empty_trace_id_outside_http_request():
    logger = CapturingLogger()

    logger.emit_event(
        LogLevel.INFO,
        message="background task",
        service="icore-agent",
        timestamp=datetime(2026, 5, 14, tzinfo=UTC),
    )

    assert logger.events[0].trace_id == ""
