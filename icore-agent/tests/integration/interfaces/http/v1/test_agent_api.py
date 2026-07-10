"""Integration-style tests for the orchestrator and API layer.

All LLM calls and external services are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from icore_agent.contexts.agent.domain.loop import ModelStepResult
from icore_agent.contexts.agent.domain.prompt import PromptEnvelope
from icore_agent.contexts.agent.domain.session import AgentMessageItem
from icore_agent.main import app
from tests.integration.interfaces.http.v1._account_support import (
    register_trial_direct,
)
from tests.integration.interfaces.http.v1._account_support import (
    trial_headers as _auth_headers,
)
from tests.support.http import ASGISyncTestClient
from tests.support.http import api_data as _api_data

# ── TestClient (sync) ──────────────────────────────────────────────────────


@pytest.fixture()
def client():
    return ASGISyncTestClient(app)


class _StaticModelClient:
    """Model client fake that returns a configured assistant reply."""

    def __init__(self, reply: str) -> None:
        """Create a static reply model client."""
        self._reply = reply

    async def sample(self, envelope: PromptEnvelope) -> ModelStepResult:
        """Return the configured assistant reply for any prompt."""
        _ = envelope
        return ModelStepResult(
            assistant_item=AgentMessageItem(text=self._reply),
        )


# ── Chat endpoint (non-streaming) ─────────────────────────────────────────

@patch("icore_agent.interfaces.http.v1.dependencies.create_chat_completions_model_client")
@patch("icore_agent.interfaces.http.v1.dependencies.memory")
def test_chat_non_streaming(mock_memory, mock_create_orch, client):
    mock_memory.get_context = AsyncMock(return_value=("", []))
    mock_memory.append_message = AsyncMock()

    mock_create_orch.return_value = _StaticModelClient(
        "Hello from iCore Agent!")

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


@patch("icore_agent.interfaces.http.v1.dependencies.create_chat_completions_model_client")
@patch("icore_agent.interfaces.http.v1.dependencies.memory")
def test_chat_requires_account_token(mock_memory, mock_create_orch, client):
    """The composed agent chat route should enforce account authentication."""
    mock_memory.get_context = AsyncMock(return_value=(None, []))
    mock_memory.append_message = AsyncMock()
    mock_create_orch.return_value = _StaticModelClient("secured reply")

    unauthorized = client.post(
        "/api/v1/agent/chat",
        json={
            "message": "Hello",
            "stream": False,
            "session_id": "secure-session",
        },
    )
    assert unauthorized.status_code == 401

    authorized = client.post(
        "/api/v1/agent/chat",
        headers=_auth_headers(client),
        json={
            "message": "Hello",
            "stream": False,
            "session_id": "secure-session",
        },
    )
    assert authorized.status_code == 200
    assert _api_data(authorized)["reply"] == "secured reply"


# ── Removed sequential endpoint ────────────────────────────────────────────

def test_sequential_endpoint_is_not_registered(client):
    """The legacy mini-SWE sequential API is no longer an agent entrypoint."""
    resp = client.post(
        "/api/v1/agent/sequential",
        json={"task": "ls -la", "use_docker": False},
        headers=_auth_headers(client),
    )

    assert resp.status_code == 404


# ── Session clear endpoint ─────────────────────────────────────────────────

@patch("icore_agent.interfaces.http.v1.dependencies.agent_session_service.soft_delete_session")
@patch("icore_agent.interfaces.http.v1.dependencies.agent_session_service.assert_owned_session")
@patch(
    "icore_agent.contexts.agent.interfaces.http.v1.handlers.session._run_session_end_extract_from_context",
    new_callable=AsyncMock,
)
@patch(
    "icore_agent.contexts.agent.interfaces.http.v1.handlers.session.resolve_session_extract_context",
    new_callable=AsyncMock,
)
@patch("icore_agent.contexts.agent.interfaces.http.v1.handlers.session.memory")
def test_clear_session(mock_memory, mock_resolve, mock_extract, _assert_owned, _soft_delete, client):
    mock_memory.clear = AsyncMock()
    mock_resolve.return_value = (
        "summary", [{"role": "user", "content": "hello"}])
    resp = client.delete("/api/v1/agent/session/my-session",
                         headers=_auth_headers(client))
    assert resp.status_code == 200
    assert _api_data(resp)["cleared"] is True
    mock_resolve.assert_awaited_once()
    _soft_delete.assert_called_once()
    mock_memory.clear.assert_awaited_once_with("my-session")
    mock_extract.assert_awaited_once()


@patch("icore_agent.interfaces.http.v1.dependencies.agent_session_service.assert_owned_session")
@patch(
    "icore_agent.contexts.agent.interfaces.http.v1.handlers.session._run_finalize_session_extract",
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


@patch("icore_agent.contexts.agent.interfaces.http.v1.handlers.session.memory")
def test_can_fetch_session_state(mock_memory, client):
    """Authenticated users should fetch canonical agent session state."""
    from icore_agent.contexts.agent.application import AgentSessionService

    user_payload = register_trial_direct(client)
    headers = {"Authorization": f"Bearer {user_payload['access_token']}"}
    AgentSessionService().ensure_owned_session(
        "demo-session",
        user_payload["user"]["id"],
        title="Demo session",
    )
    mock_memory.get_context = AsyncMock(return_value=(
        "Summary text",
        [
            {"role": "user", "content": "Research this market"},
            {"role": "assistant", "content": "Here is the review"},
        ],
    ))

    response = client.get(
        "/api/v1/agent/session/demo-session",
        headers=headers,
    )

    assert response.status_code == 200
    payload = _api_data(response)
    assert payload["session_id"] == "demo-session"
    assert payload["summary"] == "Summary text"
    assert payload["turns"] == []
    assert "messages" not in payload
    assert payload["attachments"] == []
