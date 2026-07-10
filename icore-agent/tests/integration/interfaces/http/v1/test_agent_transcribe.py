from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from icore_agent.main import app
from tests.integration.interfaces.http.v1._account_support import trial_headers
from tests.support.http import ASGISyncTestClient, api_data, api_message


@pytest.fixture()
def client():
    return ASGISyncTestClient(app)


@patch("icore_agent.contexts.agent.interfaces.http.v1.handlers.transcribe.prepare_audio_for_zai_asr")
@patch("icore_agent.contexts.agent.interfaces.http.v1.handlers.transcribe._zai_transcribe", new_callable=AsyncMock)
def test_transcribe_converts_webm_before_zai(mock_zai, mock_prepare, client):
    mock_prepare.return_value = (b"RIFFwav", "speech.wav", "audio/wav")
    mock_zai.return_value = "hello world"
    headers = trial_headers(client)
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
    headers = trial_headers(client)
    resp = client.post(
        "/api/v1/agent/transcribe",
        files={"file": ("note.webm", b"\xfffake", "audio/webm")},
        data={"language": "zh-CN"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.TEXT
    assert api_data(resp) == {"text": "hello world"}
    mock_zai.assert_awaited_once()
    call_kw = mock_zai.await_args.kwargs
    assert call_kw["language"] == "zh"


@patch("icore_agent.contexts.agent.interfaces.http.v1.handlers.transcribe.settings")
def test_zai_transcribe_requires_api_key(mock_settings, client):
    mock_settings.zai_api_key = ""
    headers = trial_headers(client)
    resp = client.post(
        "/api/v1/agent/transcribe",
        files={"file": ("note.wav", b"RIFF", "audio/wav")},
        headers=headers,
    )
    assert resp.status_code == 503
    assert "Z.AI API key" in api_message(resp)


def test_transcribe_requires_auth(client):
    resp = client.post(
        "/api/v1/agent/transcribe",
        files={"file": ("a.webm", b"x", "audio/webm")},
    )
    assert resp.status_code == 401
