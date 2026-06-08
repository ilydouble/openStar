"""Prompt fragments describing tools available to the main agent."""

from __future__ import annotations

from collections.abc import Sequence

from icore_agent.application.agent.tool.tool_definition import ToolDefinition


def build_tools_prompt(tools: Sequence[ToolDefinition] | None) -> str:
    """Build the tool snippet section for the top-level orchestrator prompt."""
    prompt_tools = _tools_with_snippets(tools)
    if not prompt_tools:
        return ""

    lines = ["## Tools available"]
    for tool in prompt_tools:
        snippet = str(tool.prompt_snippet or "").strip()
        lines.append(f"- {tool.name}: {snippet}")

    lines.extend([
        "",
        "## Tool-use rules",
        "1. Use tools only when they materially improve the answer.",
        "2. For pure conversational replies that require no tool use, respond directly.",
        "3. Combine tool results into a clear, user-facing final answer.",
        "4. Do not forward raw tool output without explaining the result.",
    ])
    return "\n".join(lines)


def _tools_with_snippets(
    tools: Sequence[ToolDefinition] | None,
) -> list[ToolDefinition]:
    """Return tools that expose prompt snippets, preserving first-seen order."""
    seen: set[str] = set()
    selected: list[ToolDefinition] = []
    for tool in tools or ():
        if not tool.prompt_snippet:
            continue
        if tool.name in seen:
            continue
        seen.add(tool.name)
        selected.append(tool)
    return selected
