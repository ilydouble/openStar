from __future__ import annotations

import httpx
import pytest
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from icore_agent.interfaces.http.v1.envelope import ApiEnvelopeRoute, install_api_envelope


def _build_app() -> FastAPI:
    """Build a minimal app with the HTTP v1 ApiEnvelope adapter installed."""
    app = FastAPI()
    install_api_envelope(app)
    router = APIRouter(route_class=ApiEnvelopeRoute)

    @router.get("/api/v1/probe")
    async def probe() -> dict[str, bool]:
        """Return a small JSON payload."""
        return {"ok": True}

    @router.get("/health")
    async def health() -> dict[str, str]:
        """Return a liveness payload."""
        return {"status": "ok"}

    @router.get("/api/v1/already-wrapped")
    async def already_wrapped() -> dict[str, object]:
        """Return an existing ApiEnvelope payload."""
        return {
            "code": 200,
            "message": "操作成功",
            "data": {"ok": True},
            "timestamp": "2026-05-21T00:00:00+00:00",
        }

    @router.get("/api/v1/fail")
    async def fail() -> None:
        """Raise an HTTP exception to exercise error wrapping."""
        raise HTTPException(status_code=400, detail="bad input")

    @router.get("/api/v1/events")
    async def events() -> StreamingResponse:
        """Return a streaming response that must not be envelope-wrapped."""

        async def stream():
            """Yield one SSE frame."""
            yield "data: ok\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream")

    app.include_router(router)

    @app.get("/outside")
    async def outside() -> dict[str, bool]:
        """Return JSON outside the v1 contract surface."""
        return {"ok": True}

    return app


@pytest.mark.asyncio
async def test_v1_json_success_is_wrapped_in_api_envelope() -> None:
    """HTTP v1 JSON success responses should use ApiEnvelope."""
    transport = httpx.ASGITransport(app=_build_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/probe")

    payload = response.json()
    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["message"] == "操作成功"
    assert payload["data"] == {"ok": True}
    assert payload["timestamp"]


@pytest.mark.asyncio
async def test_health_json_is_wrapped_in_api_envelope() -> None:
    """Health JSON should follow the same v1 ApiEnvelope contract."""
    transport = httpx.ASGITransport(app=_build_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["data"] == {"status": "ok"}


@pytest.mark.asyncio
async def test_v1_json_error_is_wrapped_in_api_envelope() -> None:
    """HTTP v1 JSON errors should put details in the ApiEnvelope message."""
    transport = httpx.ASGITransport(app=_build_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/fail")

    payload = response.json()
    assert response.status_code == 400
    assert payload["code"] == 400
    assert payload["message"] == "bad input"
    assert payload["data"] is None
    assert "error_reason" not in payload
    assert "error" + "_code" not in payload
    assert payload["timestamp"]


@pytest.mark.asyncio
async def test_existing_api_envelope_is_not_wrapped_twice() -> None:
    """Already wrapped payloads should pass through unchanged."""
    transport = httpx.ASGITransport(app=_build_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/already-wrapped")

    assert response.json() == {
        "code": 200,
        "message": "操作成功",
        "data": {"ok": True},
        "timestamp": "2026-05-21T00:00:00+00:00",
    }


@pytest.mark.asyncio
async def test_non_json_and_non_v1_responses_are_not_wrapped() -> None:
    """Streams and non-v1 paths should preserve their original response body."""
    transport = httpx.ASGITransport(app=_build_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        stream_response = await client.get("/api/v1/events")
        outside_response = await client.get("/outside")

    assert stream_response.text == "data: ok\n\n"
    assert outside_response.json() == {"ok": True}
