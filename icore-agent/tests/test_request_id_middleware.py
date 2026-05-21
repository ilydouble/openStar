from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI, Request

from icore_agent.shared.http.middleware import RequestIdMiddleware
from icore_agent.shared.http.request.request_context import get_request_id


def _build_app(*, fail: bool = False) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/inspect")
    async def inspect(request: Request):
        if fail:
            raise RuntimeError("boom")
        return {
            "context_request_id": get_request_id(),
            "state_request_id": request.state.request_id,
        }

    _ = inspect
    return app


@pytest.mark.asyncio
async def test_request_id_middleware_prefers_x_request_id_and_resets_context():
    transport = httpx.ASGITransport(app=_build_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/inspect", headers={"X-Request-ID": "req-123"})

    assert response.status_code == 200
    assert response.json() == {
        "context_request_id": "req-123",
        "state_request_id": "req-123",
    }
    assert response.headers["X-Request-ID"] == "req-123"
    assert get_request_id() is None


@pytest.mark.asyncio
async def test_request_id_middleware_falls_back_to_correlation_id():
    transport = httpx.ASGITransport(app=_build_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/inspect", headers={"X-Correlation-ID": "corr-456"})

    assert response.status_code == 200
    assert response.json()["context_request_id"] == "corr-456"
    assert response.headers["X-Request-ID"] == "corr-456"


@pytest.mark.asyncio
async def test_request_id_middleware_extracts_traceparent_trace_id():
    transport = httpx.ASGITransport(app=_build_app())
    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/inspect",
            headers={"traceparent": f"00-{trace_id}-00f067aa0ba902b7-01"},
        )

    assert response.status_code == 200
    assert response.json()["context_request_id"] == trace_id
    assert response.headers["X-Request-ID"] == trace_id


@pytest.mark.asyncio
async def test_request_id_middleware_generates_request_id_when_headers_are_absent():
    transport = httpx.ASGITransport(app=_build_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/inspect")

    generated = response.json()["context_request_id"]
    assert response.status_code == 200
    assert len(generated) == 32
    assert response.json()["state_request_id"] == generated
    assert response.headers["X-Request-ID"] == generated


@pytest.mark.asyncio
async def test_request_id_middleware_resets_context_when_endpoint_raises():
    transport = httpx.ASGITransport(app=_build_app(
        fail=True), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/inspect", headers={"X-Request-ID": "req-error"})

    assert response.status_code == 500
    assert get_request_id() is None
