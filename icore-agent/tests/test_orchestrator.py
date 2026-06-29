"""Integration-style tests for the orchestrator and API layer.

All LLM calls and external services are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from icore_agent.domain.agent.prompt import (
    PromptEnvelope,
    build_base_instructions,
)
from icore_agent.domain.agent.tool import ToolDefinition
from icore_agent.application.agent.tool.catalog import (
    build_orchestrator_tool_definitions,
)
from icore_agent.config import ResolvedLiteLLMConfig
from icore_agent.domain.agent.session import (
    AgentMessageItem,
)
from icore_agent.domain.agent.loop import ModelStepResult
from icore_agent.infrastructure.agent.chat_completions import (
    ChatCompletionsModelClient,
    create_chat_completions_model_client,
)
from icore_agent.main import app
from .test_account_flow import ASGISyncTestClient

# ── TestClient (sync) ──────────────────────────────────────────────────────


@pytest.fixture()
def client():
    return ASGISyncTestClient(app)


def _auth_headers(client: ASGISyncTestClient) -> dict[str, str]:
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


# ── Sequential endpoint ────────────────────────────────────────────────────

@patch("icore_agent.interfaces.http.v1.agent.handlers.sequential.SequentialAgent")
def test_sequential_endpoint_success(mock_seq_cls, client):
    from icore_agent.application.agent.sequential.agent import SequentialResult
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

@patch("icore_agent.interfaces.http.v1.dependencies.agent_session_service.soft_delete_session")
@patch("icore_agent.interfaces.http.v1.dependencies.agent_session_service.assert_owned_session")
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

@patch("icore_agent.infrastructure.agent.chat_completions.runner.settings")
def test_create_chat_completions_model_client_uses_resolved_model(mock_settings):
    """Chat Completions model client should use resolved LiteLLM settings."""
    mock_settings.effective_model_id.return_value = "test-model"
    mock_settings.agent_max_tokens = 123
    mock_settings.agent_temperature = 0.2
    mock_settings.resolve_litellm_config.return_value = ResolvedLiteLLMConfig(
        model_id="test-model",
        client_args={"api_key": "secret"},
        params={"max_tokens": 123, "temperature": 0.2},
    )

    model_client = create_chat_completions_model_client(
        session_id="session-1",
        user_id="user-1",
    )

    assert isinstance(model_client, ChatCompletionsModelClient)
    mock_settings.resolve_litellm_config.assert_called_once_with(
        model_id="test-model",
        user_id="user-1",
        session_id="session-1",
        max_tokens=123,
        temperature=0.2,
    )


def test_orchestrator_prompt_builder_uses_only_base_and_tool_rules():
    """System prompt should include base policy and generic tool behavior."""
    _ = build_orchestrator_tool_definitions(session_id="session-1")
    prompt = build_base_instructions()

    assert "You are iCore Agent" in prompt
    assert "Tool-use rules" in prompt
    assert "web_search" not in prompt
    assert "run_python_snippet" not in prompt
    assert "read_uploaded_file" not in prompt
    assert "chroma_search" not in prompt
    assert "generate_image" not in prompt
    assert "data_agent_tool" not in prompt
    assert "sub-agent" not in prompt
    assert "The user clicked the Data shortcut" not in prompt
    assert "Inline doc text" not in prompt
    assert "Earlier summary" not in prompt
    assert "## About this user" not in prompt


def test_system_prompt_omits_tool_prompt_snippets():
    """Tool snippets should not be rendered into the system prompt."""

    def _execute(*_: object) -> str:
        """Return a stable test result."""
        return "ok"

    _ = [
        ToolDefinition(
            name="visible_tool",
            label="Visible tool",
            description="Visible test tool.",
            parameters={"type": "object"},
            execute=_execute,
            prompt_snippet="Use visible tool when needed.",
        ),
        ToolDefinition(
            name="hidden_tool",
            label="Hidden tool",
            description="Hidden test tool.",
            parameters={"type": "object"},
            execute=_execute,
        ),
    ]
    prompt = build_base_instructions()

    assert "Tool-use rules" in prompt
    assert "visible_tool" not in prompt
    assert "Use visible tool when needed." not in prompt
    assert "hidden_tool" not in prompt
