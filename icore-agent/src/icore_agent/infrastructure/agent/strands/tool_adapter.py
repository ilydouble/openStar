"""Strands adapters for application-owned tool definitions."""

from __future__ import annotations

import inspect
import json
from typing import Any

from strands.types.tools import (
    AgentTool as StrandsAgentTool,
    ToolGenerator,
    ToolResult,
    ToolSpec,
    ToolUse,
)

from icore_agent.application.agent.tool import (
    PreparedArguments,
    ToolDefinition,
    ToolExecutionContext,
)


class AgentTool(StrandsAgentTool):
    """Adapter from ToolDefinition to the Strands AgentTool interface."""

    def __init__(self, definition: ToolDefinition) -> None:
        """Create a Strands-compatible tool from a structured definition."""
        super().__init__()
        self.definition = definition

    @property
    def tool_name(self) -> str:
        """Return the model-facing tool name."""
        return self.definition.name

    @property
    def tool_spec(self) -> ToolSpec:
        """Return the Strands tool specification sent to the model."""
        return {
            "name": self.definition.name,
            "description": self.definition.description,
            "inputSchema": {"json": self.definition.parameters},
        }

    @property
    def tool_type(self) -> str:
        """Return the implementation type reported to Strands."""
        return "python"

    async def stream(
        self,
        tool_use: ToolUse,
        invocation_state: dict[str, Any],
        **_: Any,
    ) -> ToolGenerator:
        """Execute the tool once and yield a final public Strands ToolResult."""
        tool_call_id = str(tool_use.get("toolUseId") or "")
        try:
            arguments = self._prepare_arguments(tool_use.get("input"))
            context = ToolExecutionContext(
                tool_call_id=tool_call_id,
                invocation_state=invocation_state,
            )
            result = self.definition.execute(tool_call_id, arguments, context)
            if inspect.isawaitable(result):
                result = await result
            yield _success_result(tool_call_id, result)
        except Exception as exc:
            yield _error_result(tool_call_id, exc)

    def _prepare_arguments(self, raw_input: Any) -> PreparedArguments:
        """Normalize and optionally validate raw model-supplied arguments."""
        if self.definition.prepare_arguments is not None:
            return self.definition.prepare_arguments(raw_input)
        if raw_input is None:
            return {}
        if not isinstance(raw_input, dict):
            raise TypeError(
                f"tool {self.definition.name!r} input must be an object"
            )
        return dict(raw_input)


def make_agent_tool(definition: ToolDefinition) -> AgentTool:
    """Build an AgentTool adapter for one ToolDefinition."""
    return AgentTool(definition)


def _success_result(tool_call_id: str, value: Any) -> ToolResult:
    """Normalize executor output into a successful Strands ToolResult."""
    if isinstance(value, dict) and {"content", "status"}.issubset(value):
        return {
            "toolUseId": str(value.get("toolUseId") or tool_call_id),
            "status": value.get("status", "success"),
            "content": value.get("content") or [],
        }
    return {
        "toolUseId": tool_call_id,
        "status": "success",
        "content": [{"text": _result_text(value)}],
    }


def _error_result(tool_call_id: str, exc: Exception) -> ToolResult:
    """Build a public error ToolResult from an executor exception."""
    return {
        "toolUseId": tool_call_id,
        "status": "error",
        "content": [{"text": str(exc)}],
    }


def _result_text(value: Any) -> str:
    """Convert arbitrary executor output into model-readable text."""
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)
