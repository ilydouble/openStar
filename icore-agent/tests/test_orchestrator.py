"""Integration-style tests for the orchestrator and API layer.

All LLM calls and external services are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from icore_agent.application.agent.sys_prompt import (
    BuildSystemPromptOptions,
    build_system_prompt,
)
from icore_agent.application.agent.tool import AgentTool, ToolDefinition
from icore_agent.application.agent.tool.catalog import (
    build_orchestrator_tool_definitions,
)
from icore_agent.application.agent.runner.orchestrator import create_orchestrator
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

@patch("icore_agent.application.agent.runner.model_factory.LiteLLMModel")
@patch("icore_agent.application.agent.runner.orchestrator.Agent")
def test_create_orchestrator_uses_correct_model(mock_agent_cls, mock_model_cls):
    from icore_agent.config import settings

    create_orchestrator()
    _, model_kwargs = mock_model_cls.call_args
    assert model_kwargs["model_id"] == settings.model_id
    assert "client_args" in model_kwargs
    assert model_kwargs["params"]["max_tokens"] == settings.agent_max_tokens
    assert model_kwargs["params"]["temperature"] == settings.agent_temperature
    assert "api_key" not in model_kwargs["params"]
    mock_agent_cls.assert_called_once()
    # Verify direct main-agent tools are registered.
    _, kwargs = mock_agent_cls.call_args
    tools = kwargs.get("tools", [])
    assert len(tools) == 11
    assert all(isinstance(tool, AgentTool) for tool in tools)
    assert "web_search" in kwargs["system_prompt"]


def test_orchestrator_prompt_builder_uses_only_base_and_tools():
    """System prompt should include only base policy and direct tool info."""
    prompt = str(build_system_prompt(BuildSystemPromptOptions(
        tools=build_orchestrator_tool_definitions(session_id="session-1"),
        summary="Earlier summary",
        attachments_text="Inline doc text",
        user_memory_prompt="## About this user\n- tone: concise",
    )))

    assert "You are iCore Agent" in prompt
    assert "web_search" in prompt
    assert "run_python_snippet" in prompt
    assert "chroma_search" in prompt
    assert "generate_image" in prompt
    assert "data_agent_tool" not in prompt
    assert "sub-agent" not in prompt
    assert "The user clicked the Data shortcut" not in prompt
    assert "Inline doc text" not in prompt
    assert "Earlier summary" not in prompt
    assert "## About this user" not in prompt


def test_system_prompt_includes_only_tool_prompt_snippets():
    """Only tools with prompt snippets should appear in the prompt tool list."""

    def _execute(*_: object) -> str:
        """Return a stable test result."""
        return "ok"

    prompt = str(build_system_prompt(BuildSystemPromptOptions(tools=[
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
    ])))

    assert "visible_tool: Use visible tool when needed." in prompt
    assert "hidden_tool" not in prompt
