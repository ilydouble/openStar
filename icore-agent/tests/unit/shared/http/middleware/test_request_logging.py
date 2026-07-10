from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from fastapi import FastAPI, Request, Response

from icore_agent.shared.http.middleware import (
    BackendRequestLoggingMiddleware,
    RequestIdMiddleware,
)
from icore_agent.shared.logging.contracts.v1 import LogEvent, LogLevel
from icore_agent.shared.logging.logging_service_client import LoggingServiceClient


class CapturingLoggingClient(LoggingServiceClient):
    """Logging-service client double that records backend request events."""

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


def _build_app(
    logging_client: CapturingLoggingClient,
    *,
    fail: bool = False,
    health_status: int = 200,
) -> FastAPI:
    """Build a small ASGI app with backend access logging enabled."""
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        BackendRequestLoggingMiddleware,
        client=logging_client,
        now=lambda: datetime(2026, 5, 16, 7, 30, tzinfo=UTC),
    )

    @app.get("/inspect")
    async def inspect(request: Request):
        if fail:
            raise RuntimeError("boom")
        request.state.user = {"id": "user-1", "roles": ["owner", "admin"]}
        return {"ok": True}

    @app.get("/health")
    async def health():
        """Return a configurable health probe response."""
        if health_status >= 400:
            return Response(status_code=health_status)
        return {"status": "ok"}

    @app.get("/ready")
    async def ready():
        """Return a successful readiness probe response."""
        return {"status": "ready"}

    _ = inspect
    _ = health
    _ = ready
    return app


@pytest.mark.asyncio
async def test_backend_request_logging_middleware_emits_success_event():
    """Verify successful non-health HTTP requests are sent to logging-service."""
    logging_client = CapturingLoggingClient()
    transport = httpx.ASGITransport(app=_build_app(logging_client))

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        response = await http_client.get(
            "/inspect?source=frontend",
            headers={
                "X-Request-ID": "req-backend-1",
                "X-Forwarded-For": "203.0.113.10, 10.0.0.5",
                "User-Agent": "pytest-client",
            },
        )

    assert response.status_code == 200
    assert len(logging_client.events) == 1
    event = logging_client.events[0]
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
async def test_backend_request_logging_middleware_skips_successful_health_probe():
    """Verify successful health probes do not emit routine backend access logs."""
    logging_client = CapturingLoggingClient()
    transport = httpx.ASGITransport(app=_build_app(logging_client))

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        health_response = await http_client.get("/health")
        ready_response = await http_client.get("/ready")

    assert health_response.status_code == 200
    assert ready_response.status_code == 200
    assert logging_client.events == []


@pytest.mark.asyncio
async def test_backend_request_logging_middleware_logs_failed_health_probe():
    """Verify failed health probes still emit backend access logs for diagnosis."""
    logging_client = CapturingLoggingClient()
    transport = httpx.ASGITransport(
        app=_build_app(logging_client, health_status=503))

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        response = await http_client.get(
            "/health",
            headers={"X-Request-ID": "req-health-failed"},
        )

    assert response.status_code == 503
    assert len(logging_client.events) == 1
    event = logging_client.events[0]
    assert event.level == LogLevel.ERROR
    assert event.trace_id == "req-health-failed"
    assert event.metadata["path"] == "/health"
    assert event.metadata["final_status_code"] == 503


@pytest.mark.asyncio
async def test_backend_request_logging_middleware_emits_error_event():
    """Verify unhandled backend errors are logged before FastAPI returns 500."""
    logging_client = CapturingLoggingClient()
    transport = httpx.ASGITransport(
        app=_build_app(logging_client, fail=True),
        raise_app_exceptions=False,
    )

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        response = await http_client.get(
            "/inspect",
            headers={"X-Request-ID": "req-backend-error"},
        )

    assert response.status_code == 500
    assert len(logging_client.events) == 1
    event = logging_client.events[0]
    assert event.level == LogLevel.ERROR
    assert event.service == "icore-backend"
    assert event.trace_id == "req-backend-error"
    assert event.metadata["final_status_code"] == 500
    assert event.metadata["error_type"] == "RuntimeError"
