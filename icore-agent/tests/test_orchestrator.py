"""Integration-style tests for the orchestrator and API layer.

All LLM calls and external services are mocked.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from icore_agent.main import app
from icore_agent.engine.orchestrator import create_orchestrator


# ── TestClient (sync) ──────────────────────────────────────────────────────

@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _auth_headers(client: TestClient) -> dict[str, str]:
    from .test_account_flow import _register_trial_direct

    payload = _register_trial_direct(client)
    return {"Authorization": f"Bearer {payload['access_token']}"}


# ── Health endpoints ───────────────────────────────────────────────────────

def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_ready_returns_ready(client):
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


# ── Chat endpoint (non-streaming) ─────────────────────────────────────────

@patch("icore_agent.api.routers.agent.create_orchestrator")
@patch("icore_agent.api.routers.agent.attachments")
@patch("icore_agent.api.routers.agent.memory")
def test_chat_non_streaming(mock_memory, mock_attachments, mock_create_orch, client):
    mock_memory.get_context = AsyncMock(return_value=("", []))
    mock_memory.append_message = AsyncMock()
    mock_attachments.get_inline_text = AsyncMock(return_value="")
    mock_attachments.has_rag_docs = AsyncMock(return_value=False)
    mock_attachments.get_image_refs = AsyncMock(return_value=[])
    mock_attachments.get_data_refs = AsyncMock(return_value=[])

    mock_agent = MagicMock(return_value="Hello from iCore Agent!")
    mock_create_orch.return_value = mock_agent

    resp = client.post(
        "/api/v1/agent/chat",
        json={"message": "Hello", "stream": False, "session_id": "test-session"},
        headers=_auth_headers(client),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["reply"] == "Hello from iCore Agent!"
    assert data["session_id"] == "test-session"


# ── Sequential endpoint ────────────────────────────────────────────────────

@patch("icore_agent.api.routers.agent.SequentialAgent")
def test_sequential_endpoint_success(mock_seq_cls, client):
    from icore_agent.engine.sequential.agent import SequentialResult
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
    data = resp.json()
    assert data["status"] == "complete"
    assert data["steps"] == 2


# ── Session clear endpoint ─────────────────────────────────────────────────

@patch("icore_agent.api.routers.agent.attachments")
@patch("icore_agent.api.routers.agent.memory")
def test_clear_session(mock_memory, mock_attachments, client):
    mock_memory.clear = AsyncMock()
    mock_attachments.clear = AsyncMock()
    resp = client.delete("/api/v1/agent/session/my-session", headers=_auth_headers(client))
    assert resp.status_code == 200
    assert resp.json()["cleared"] is True
    mock_memory.clear.assert_awaited_once_with("my-session")
    mock_attachments.clear.assert_awaited_once_with("my-session")


# ── Orchestrator factory ───────────────────────────────────────────────────

@patch("icore_agent.engine.orchestrator.LiteLLMModel")
@patch("icore_agent.engine.orchestrator.Agent")
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
