"""Tests for agent-owned base model instructions."""

from icore_agent.contexts.agent.application.tool.catalog import (
    build_orchestrator_tool_definitions,
)
from icore_agent.contexts.agent.domain.prompt import build_base_instructions
from icore_agent.contexts.agent.domain.tool import ToolDefinition


def test_orchestrator_prompt_excludes_user_memory_section() -> None:
    """System prompt should not include runtime user memory context."""
    prompt = build_base_instructions()
    assert "## About this user" not in prompt
    assert "Session summary" not in prompt


def test_orchestrator_prompt_builder_uses_only_base_and_tool_rules() -> None:
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


def test_system_prompt_omits_tool_prompt_snippets() -> None:
    """Tool snippets should not be rendered into the system prompt."""

    def execute(*_: object) -> str:
        """Return a stable test result."""
        return "ok"

    _ = [
        ToolDefinition(
            name="visible_tool",
            label="Visible tool",
            description="Visible test tool.",
            parameters={"type": "object"},
            execute=execute,
            prompt_snippet="Use visible tool when needed.",
        ),
        ToolDefinition(
            name="hidden_tool",
            label="Hidden tool",
            description="Hidden test tool.",
            parameters={"type": "object"},
            execute=execute,
        ),
    ]
    prompt = build_base_instructions()

    assert "Tool-use rules" in prompt
    assert "visible_tool" not in prompt
    assert "Use visible tool when needed." not in prompt
    assert "hidden_tool" not in prompt
