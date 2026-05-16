from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from fastapi import FastAPI, Request

from icore_agent.lib.http.middleware import (
    BackendRequestLoggingMiddleware,
    RequestIdMiddleware,
)
from icore_agent.lib.logging.contracts.v1 import LogEvent, LogLevel
from icore_agent.lib.logging.logger import Logger


class CapturingLogger(Logger):
    """Logger double that records backend request events in memory."""

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


def _build_app(logger: CapturingLogger, *, fail: bool = False) -> FastAPI:
    """Build a small ASGI app with backend access logging enabled."""
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        BackendRequestLoggingMiddleware,
        logger=logger,
        now=lambda: datetime(2026, 5, 16, 7, 30, tzinfo=UTC),
    )

    @app.get("/inspect")
    async def inspect(request: Request):
        if fail:
            raise RuntimeError("boom")
        request.state.user = {"id": "user-1", "roles": ["owner", "admin"]}
        return {"ok": True}

    _ = inspect
    return app


@pytest.mark.asyncio
async def test_backend_request_logging_middleware_emits_success_event():
    """Verify every successful backend HTTP request is sent to logging-service."""
    logger = CapturingLogger()
    transport = httpx.ASGITransport(app=_build_app(logger))

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/inspect?source=frontend",
            headers={
                "X-Request-ID": "req-backend-1",
                "X-Forwarded-For": "203.0.113.10, 10.0.0.5",
                "User-Agent": "pytest-client",
            },
        )

    assert response.status_code == 200
    assert len(logger.events) == 1
    event = logger.events[0]
    assert event.level == LogLevel.INFO
    assert event.service == "icore-backend"
    assert event.message == "backend request"
    assert event.trace_id == "req-backend-1"
    assert event.metadata["request_id"] == "req-backend-1"
    assert event.metadata["method"] == "GET"
    assert event.metadata["path"] == "/inspect"
    assert event.metadata["query"] == "source=frontend"
    assert event.metadata["client_ip"] == "203.0.113.10"
    assert event.metadata["user_agent"] == "pytest-client"
    assert event.metadata["user_id"] == "user-1"
    assert event.metadata["roles"] == ["owner", "admin"]
    assert event.metadata["final_status_code"] == 200
    assert event.metadata["request_elapsed_time"] >= 0
    assert event.metadata["error_type"] is None


@pytest.mark.asyncio
async def test_backend_request_logging_middleware_emits_error_event():
    """Verify unhandled backend errors are logged before FastAPI returns 500."""
    logger = CapturingLogger()
    transport = httpx.ASGITransport(
        app=_build_app(logger, fail=True),
        raise_app_exceptions=False,
    )

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/inspect",
            headers={"X-Request-ID": "req-backend-error"},
        )

    assert response.status_code == 500
    assert len(logger.events) == 1
    event = logger.events[0]
    assert event.level == LogLevel.ERROR
    assert event.service == "icore-backend"
    assert event.trace_id == "req-backend-error"
    assert event.metadata["final_status_code"] == 500
    assert event.metadata["error_type"] == "RuntimeError"
