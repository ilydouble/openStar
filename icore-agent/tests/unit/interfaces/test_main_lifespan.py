"""Tests for the FastAPI process lifespan."""

import asyncio
from typing import Any

from icore_agent import main


class RecordingLogger:
    """Logger double that records lifecycle messages."""

    def __init__(self, events: list[str]) -> None:
        """Store lifecycle messages in the shared event list."""
        self._events = events

    def info(self, message: str, **_: Any) -> bool:
        """Record one informational lifecycle message."""
        self._events.append(message)
        return True


class RecordingLoggingClient:
    """Logging client double that records asynchronous close calls."""

    def __init__(self, events: list[str]) -> None:
        """Store close activity in the shared event list."""
        self._events = events
        self.timeout: float | None = None

    async def aclose(self, *, timeout: float | None = None) -> bool:
        """Record the requested drain timeout."""
        self.timeout = timeout
        self._events.append("logging_client_closed")
        return True


def test_lifespan_logs_shutdown_before_draining_logging_client(monkeypatch) -> None:
    """FastAPI shutdown must enqueue its final log before closing the client."""
    events: list[str] = []
    client = RecordingLoggingClient(events)
    monkeypatch.setattr(main, "log", RecordingLogger(events))
    monkeypatch.setattr(main, "default_logging_client", client)
    monkeypatch.setattr(main.settings, "import_json_users_on_startup", False)
    monkeypatch.setattr(main.settings, "logging_client_drain_timeout", 5.0)

    async def run_lifespan() -> None:
        """Enter and exit the application lifespan once."""
        async with main.lifespan(None):
            events.append("application_running")

    asyncio.run(run_lifespan())

    assert events == [
        "icore_agent_started",
        "application_running",
        "icore_agent_stopped",
        "logging_client_closed",
    ]
    assert client.timeout == 5.0
