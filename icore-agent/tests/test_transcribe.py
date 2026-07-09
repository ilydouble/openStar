from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from icore_agent.main import app
from .test_account_flow import ASGISyncTestClient


@pytest.fixture()
def client():
    return ASGISyncTestClient(app)


def _api_data(resp) -> dict:
    """Return the ApiEnvelope data object from a test response."""
    payload = resp.json()
    assert payload["code"] == resp.status_code
    assert payload["message"]
    assert payload["timestamp"]
    return payload["data"]


def _api_message(resp) -> str:
    """Return the ApiEnvelope message from a test response."""
    payload = resp.json()
    assert payload["code"] == resp.status_code
    assert payload["timestamp"]
    return payload["message"]


def _register_trial_direct(
    client: ASGISyncTestClient,
    email: str | None = None,
    name: str = "Trial User",
) -> dict:
    from icore_agent.infrastructure.control_plane.json_store import control_plane_store

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
    return _api_data(resp)


def _trial_headers(client: ASGISyncTestClient) -> dict[str, str]:
    payload = _register_trial_direct(client)
    return {"Authorization": f"Bearer {payload['access_token']}"}


@patch("icore_agent.contexts.agent.interfaces.http.v1.handlers.transcribe.prepare_audio_for_zai_asr")
@patch("icore_agent.contexts.agent.interfaces.http.v1.handlers.transcribe._zai_transcribe", new_callable=AsyncMock)
def test_transcribe_converts_webm_before_zai(mock_zai, mock_prepare, client):
    mock_prepare.return_value = (b"RIFFwav", "speech.wav", "audio/wav")
    mock_zai.return_value = "hello world"
    headers = _trial_headers(client)
    resp = client.post(
        "/api/v1/agent/transcribe",
        files={"file": ("note.webm", b"\x1a\x45\xdf\xa3", "audio/webm")},
        data={"language": "zh-CN"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.TEXT
    mock_prepare.assert_called_once()
    mock_zai.assert_awaited_once()
    assert mock_zai.await_args.kwargs["filename"] == "speech.wav"
    assert mock_zai.await_args.kwargs["mime"] == "audio/wav"


@patch("icore_agent.contexts.agent.interfaces.http.v1.handlers.transcribe.prepare_audio_for_zai_asr")
@patch("icore_agent.contexts.agent.interfaces.http.v1.handlers.transcribe._zai_transcribe", new_callable=AsyncMock)
def test_transcribe_zai_returns_text(mock_zai, mock_prepare, client):
    mock_zai.return_value = "hello world"
    mock_prepare.return_value = (b"RIFFwav", "speech.wav", "audio/wav")
    headers = _trial_headers(client)
    resp = client.post(
        "/api/v1/agent/transcribe",
        files={"file": ("note.webm", b"\xfffake", "audio/webm")},
        data={"language": "zh-CN"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.TEXT
    assert _api_data(resp) == {"text": "hello world"}
    mock_zai.assert_awaited_once()
    call_kw = mock_zai.await_args.kwargs
    assert call_kw["language"] == "zh"


@patch("icore_agent.contexts.agent.interfaces.http.v1.handlers.transcribe.settings")
def test_zai_transcribe_url_uses_configured_base(mock_settings):
    from icore_agent.contexts.agent.interfaces.http.v1.handlers.transcribe import _zai_transcribe_url

    mock_settings.zai_base_url = "https://open.bigmodel.cn/api/paas/v4/"
    assert _zai_transcribe_url() == "https://open.bigmodel.cn/api/paas/v4/audio/transcriptions"


@patch("icore_agent.contexts.agent.interfaces.http.v1.handlers.transcribe.settings")
def test_zai_transcribe_requires_api_key(mock_settings, client):
    mock_settings.zai_api_key = ""
    headers = _trial_headers(client)
    resp = client.post(
        "/api/v1/agent/transcribe",
        files={"file": ("note.wav", b"RIFF", "audio/wav")},
        headers=headers,
    )
    assert resp.status_code == 503
    assert "Z.AI API key" in _api_message(resp)


@pytest.mark.asyncio
@patch("icore_agent.contexts.agent.interfaces.http.v1.handlers.transcribe.settings")
async def test_zai_transcribe_calls_glm_asr_endpoint(mock_settings):
    from icore_agent.contexts.agent.interfaces.http.v1.handlers.transcribe import _zai_transcribe

    mock_settings.zai_api_key = "sk-test"
    mock_settings.zai_base_url = "https://open.bigmodel.cn/api/paas/v4/"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"text": "hello"}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("icore_agent.contexts.agent.interfaces.http.v1.handlers.transcribe.httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client_cls.return_value.__aexit__.return_value = None

        text = await _zai_transcribe(
            audio=b"audio-bytes",
            filename="speech.wav",
            mime="audio/wav",
            language="en",
        )

    assert text == "hello"
    mock_client.post.assert_awaited_once()
    url = mock_client.post.await_args.args[0]
    assert url == "https://open.bigmodel.cn/api/paas/v4/audio/transcriptions"
    assert mock_client.post.await_args.kwargs["data"]["model"] == "glm-asr-2512"
    assert mock_client.post.await_args.kwargs["data"]["stream"] == "false"
    assert mock_client.post.await_args.kwargs["headers"]["Authorization"] == "Bearer sk-test"


def test_transcribe_requires_auth(client):
    resp = client.post(
        "/api/v1/agent/transcribe",
        files={"file": ("a.webm", b"x", "audio/webm")},
    )
    assert resp.status_code == 401
