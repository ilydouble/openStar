from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from icore_agent.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _register_trial_direct(client: TestClient, email: str | None = None, name: str = "Trial User") -> dict:
    from icore_agent.control_plane import control_plane_store

    email = email or f"trial-{uuid4().hex[:8]}@example.com"
    code = "123456"
    with control_plane_store._lock:
        data = control_plane_store._load()
        data.setdefault("verification_codes", {})[email.lower()] = {
            "code": code,
            "expires_at": int(time.time()) + 600,
            "ip": "127.0.0.1",
            "timestamp": int(time.time()),
        }
        data.setdefault("ip_registrations", {}).pop("127.0.0.1", None)
        data.setdefault("ip_registrations", {}).pop("testclient", None)
        control_plane_store._save(data)

    resp = client.post(
        "/api/v1/account/register-trial",
        json={"name": name, "email": email, "verification_code": code},
    )
    assert resp.status_code == 200, resp.json()
    return resp.json()


def _trial_headers(client: TestClient) -> dict[str, str]:
    payload = _register_trial_direct(client)
    return {"Authorization": f"Bearer {payload['access_token']}"}


@patch("icore_agent.api.routers.agent._whisper_transcribe", new_callable=AsyncMock)
def test_transcribe_whisper_returns_text(mock_whisper, client):
    mock_whisper.return_value = "hello world"
    headers = _trial_headers(client)
    resp = client.post(
        "/api/v1/agent/transcribe",
        files={"file": ("note.webm", b"\xfffake", "audio/webm")},
        data={"language": "zh-CN"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"text": "hello world"}
    mock_whisper.assert_awaited_once()
    call_kw = mock_whisper.await_args.kwargs
    assert call_kw["language"] == "zh"


def test_transcribe_requires_auth(client):
    resp = client.post(
        "/api/v1/agent/transcribe",
        files={"file": ("a.webm", b"x", "audio/webm")},
    )
    assert resp.status_code == 401
