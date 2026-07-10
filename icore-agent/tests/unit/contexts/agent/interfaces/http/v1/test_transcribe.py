"""Unit tests for the agent transcription HTTP adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@patch("icore_agent.contexts.agent.interfaces.http.v1.handlers.transcribe.settings")
def test_zai_transcribe_url_uses_configured_base(mock_settings) -> None:
    from icore_agent.contexts.agent.interfaces.http.v1.handlers.transcribe import (
        _zai_transcribe_url,
    )

    mock_settings.zai_base_url = "https://open.bigmodel.cn/api/paas/v4/"

    assert (
        _zai_transcribe_url()
        == "https://open.bigmodel.cn/api/paas/v4/audio/transcriptions"
    )


@pytest.mark.asyncio
@patch("icore_agent.contexts.agent.interfaces.http.v1.handlers.transcribe.settings")
async def test_zai_transcribe_calls_glm_asr_endpoint(mock_settings) -> None:
    from icore_agent.contexts.agent.interfaces.http.v1.handlers.transcribe import (
        _zai_transcribe,
    )

    mock_settings.zai_api_key = "sk-test"
    mock_settings.zai_base_url = "https://open.bigmodel.cn/api/paas/v4/"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"text": "hello"}
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch(
        "icore_agent.contexts.agent.interfaces.http.v1.handlers.transcribe.httpx.AsyncClient",
    ) as mock_client_class:
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client_class.return_value.__aexit__.return_value = None
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
    assert (
        mock_client.post.await_args.kwargs["headers"]["Authorization"]
        == "Bearer sk-test"
    )
