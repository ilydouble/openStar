"""Integration-style tests for the orchestrator and API layer.

All LLM calls and external services are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from icore_agent.application.chat.orchestrator import create_orchestrator
from icore_agent.application.chat.prompts import build_orchestrator_system_prompt
from icore_agent.application.chat.routing import AgentHint
from icore_agent.main import app

# ── TestClient (sync) ──────────────────────────────────────────────────────


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _auth_headers(client: TestClient) -> dict[str, str]:
    from .test_account_flow import _register_trial_direct

    payload = _register_trial_direct(client)
    return {"Authorization": f"Bearer {payload['access_token']}"}


def _api_data(resp):
    """Return the ApiEnvelope data object from a test response."""
    payload = resp.json()
    assert payload["code"] == resp.status_code
    assert payload["message"]
    assert payload["timestamp"]
    return payload["data"]


# ── Health endpoints ───────────────────────────────────────────────────────

def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = _api_data(resp)
    assert data["status"] == "ok"
    assert "version" in data


def test_ready_returns_ready(client):
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert _api_data(resp)["status"] == "ready"


# ── Chat endpoint (non-streaming) ─────────────────────────────────────────

@patch("icore_agent.interfaces.http.v1.dependencies.create_orchestrator")
@patch("icore_agent.interfaces.http.v1.dependencies.memory")
def test_chat_non_streaming(mock_memory, mock_create_orch, client):
    mock_memory.get_context = AsyncMock(return_value=("", []))
    mock_memory.append_message = AsyncMock()

    mock_agent = MagicMock(return_value="Hello from iCore Agent!")
    mock_create_orch.return_value = mock_agent

    resp = client.post(
        "/api/v1/agent/chat",
        json={"message": "Hello", "stream": False,
              "session_id": "test-session"},
        headers=_auth_headers(client),
    )
    assert resp.status_code == 200
    data = _api_data(resp)
    assert data["reply"] == "Hello from iCore Agent!"
    assert data["session_id"] == "test-session"


# ── Sequential endpoint ────────────────────────────────────────────────────

@patch("icore_agent.interfaces.http.v1.agent.handlers.sequential.SequentialAgent")
def test_sequential_endpoint_success(mock_seq_cls, client):
    from icore_agent.application.chat.sequential.agent import SequentialResult
    mock_instance = MagicMock()
    mock_instance.run.return_value = SequentialResult(
        status="complete", output="Files listed.", steps=2
    )
    mock_seq_cls.return_value = mock_instance

    resp = client.post(
        "/api/v1/agent/sequential",
        json={"task": "ls -la", "use_docker": False},
        headers=_auth_headers(client),
    )
    assert resp.status_code == 200
    data = _api_data(resp)
    assert data["status"] == "complete"
    assert data["steps"] == 2


# ── Session clear endpoint ─────────────────────────────────────────────────

@patch("icore_agent.interfaces.http.v1.dependencies.chat_history_service.soft_delete_session")
@patch("icore_agent.interfaces.http.v1.dependencies.chat_history_service.assert_owned_session")
@patch(
    "icore_agent.interfaces.http.v1.agent.handlers.session._run_session_end_extract_from_context",
    new_callable=AsyncMock,
)
@patch(
    "icore_agent.interfaces.http.v1.agent.handlers.session.resolve_session_extract_context",
    new_callable=AsyncMock,
)
@patch("icore_agent.interfaces.http.v1.agent.handlers.session.memory")
def test_clear_session(mock_memory, mock_resolve, mock_extract, _assert_owned, _soft_delete, client):
    mock_memory.clear = AsyncMock()
    mock_resolve.return_value = ("summary", [{"role": "user", "content": "hello"}])
    resp = client.delete("/api/v1/agent/session/my-session",
                         headers=_auth_headers(client))
    assert resp.status_code == 200
    assert _api_data(resp)["cleared"] is True
    mock_resolve.assert_awaited_once()
    _soft_delete.assert_called_once()
    mock_memory.clear.assert_awaited_once_with("my-session")
    mock_extract.assert_awaited_once()


@patch("icore_agent.interfaces.http.v1.dependencies.chat_history_service.assert_owned_session")
@patch(
    "icore_agent.interfaces.http.v1.agent.handlers.session._run_finalize_session_extract",
    new_callable=AsyncMock,
)
def test_finalize_session(mock_extract, _assert_owned, client):
    resp = client.post(
        "/api/v1/agent/session/my-session/finalize",
        headers=_auth_headers(client),
    )
    assert resp.status_code == 200
    data = _api_data(resp)
    assert data["finalized"] is True
    mock_extract.assert_awaited_once()


# ── Orchestrator factory ───────────────────────────────────────────────────

@patch("icore_agent.application.chat.orchestrator.LiteLLMModel")
@patch("icore_agent.application.chat.orchestrator.Agent")
def test_create_orchestrator_uses_correct_model(mock_agent_cls, mock_model_cls):
    from icore_agent.config import settings

    create_orchestrator()
    _, model_kwargs = mock_model_cls.call_args
    assert model_kwargs["model_id"] == settings.model_id
    assert model_kwargs["params"]["max_tokens"] == settings.agent_max_tokens
    assert model_kwargs["params"]["temperature"] == settings.agent_temperature
    mock_agent_cls.assert_called_once()
    # Verify 5 tools are registered
    _, kwargs = mock_agent_cls.call_args
    assert len(kwargs.get("tools", [])) == 5


def test_orchestrator_prompt_builder_includes_chat_context():
    """Application prompt policy should assemble all prepared chat context."""
    prompt = build_orchestrator_system_prompt(
        summary="Earlier summary",
        attachments_text="Inline doc text",
        image_attachments=[{"filename": "photo.png", "ref": "file-ref"}],
        data_attachments=[
            {
                "filename": "data.csv",
                "abs_path": "/tmp/data.csv",
                "columns": [{"name": "amount", "dtype": "int64"}],
                "row_count": 2,
                "preview_md": "| amount |\n| --- |\n| 10 |",
            }
        ],
        agent_hint=AgentHint.DATA,
    )

    assert "data_agent_tool" in prompt
    assert "The user clicked the Data shortcut" in prompt
    assert "Inline doc text" in prompt
    assert "photo.png" in prompt
    assert "file-ref" in prompt
    assert "data.csv" in prompt
    assert "amount(int64)" in prompt
    assert "Earlier summary" in prompt
