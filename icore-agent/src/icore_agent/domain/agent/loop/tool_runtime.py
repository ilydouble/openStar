"""Tool runtime protocol for provider-neutral agent loop execution."""

from __future__ import annotations

from typing import Protocol

from icore_agent.domain.agent.session import ToolCallItem
from icore_agent.domain.agent.tool import ToolDefinition


class ToolRuntimePort(Protocol):
    """Port for executing tools and exposing model-visible definitions."""

    def visible_tools(self) -> list[ToolDefinition]:
        """Return tool definitions visible to the model."""
        ...

    async def execute(self, tool_calls: list[ToolCallItem]) -> list[ToolCallItem]:
        """Execute requested tool calls and return completed or failed items."""
        ...
