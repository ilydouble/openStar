"""Application-level runtime for executing agent tool calls."""

from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime
from typing import Any

from icore_agent.contexts.agent.domain.session import (
    ToolCallError,
    ToolCallItem,
    ToolCallResult,
    ToolCallStatus,
)
from icore_agent.contexts.agent.domain.tool import (
    ToolDefinition,
    ToolExecutionContext,
)


class ToolRuntime:
    """Execute provider-neutral tool calls against the application tool catalog."""

    def __init__(self, tool_definitions: list[ToolDefinition]) -> None:
        """Create a runtime with executable tool definitions."""
        self._tool_definitions = {
            definition.name: definition
            for definition in tool_definitions
        }

    def visible_tools(self) -> list[ToolDefinition]:
        """Return tool definitions visible to the model."""
        return list(self._tool_definitions.values())

    async def execute(self, tool_calls: list[ToolCallItem]) -> list[ToolCallItem]:
        """Execute requested tool calls sequentially and return terminal items."""
        results: list[ToolCallItem] = []
        for tool_call in tool_calls:
            results.append(await self._execute_one(tool_call))
        return results

    async def _execute_one(self, tool_call: ToolCallItem) -> ToolCallItem:
        """Execute one tool call and normalize success or failure."""
        started_at = tool_call.started_at or datetime.now(UTC)
        definition = self._tool_definitions.get(tool_call.function.name or "")
        if definition is None:
            message = f"Unknown tool: {tool_call.function.name or 'unknown'}"
            return _failed_tool_call(
                tool_call,
                message=message,
                code="UnknownTool",
                started_at=started_at,
            )
        try:
            arguments = _prepared_arguments(definition, tool_call)
            tool_call_id = tool_call.provider_tool_call_id or tool_call.id
            result = definition.execute(
                tool_call_id,
                arguments,
                ToolExecutionContext(tool_call_id=tool_call_id),
            )
            if inspect.isawaitable(result):
                result = await result
            return _completed_tool_call(
                tool_call,
                result,
                started_at=started_at,
            )
        except Exception as exc:
            return _failed_tool_call(
                tool_call,
                message=str(exc),
                code=type(exc).__name__,
                started_at=started_at,
            )


def _prepared_arguments(
    definition: ToolDefinition,
    tool_call: ToolCallItem,
) -> dict[str, Any]:
    """Return validated arguments for a tool executor."""
    arguments = dict(tool_call.function.arguments_json or {})
    if definition.prepare_arguments is None:
        return arguments
    return definition.prepare_arguments(arguments)


def _completed_tool_call(
    tool_call: ToolCallItem,
    result: Any,
    *,
    started_at: datetime,
) -> ToolCallItem:
    """Return a completed ToolCallItem with normalized result payload."""
    completed_at = datetime.now(UTC)
    return tool_call.model_copy(update={
        "status": ToolCallStatus.COMPLETED,
        "result": ToolCallResult(
            content=_result_text(result),
            structured_content=_structured_result(result),
        ),
        "error": None,
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_ms": _duration_ms(started_at, completed_at),
    })


def _failed_tool_call(
    tool_call: ToolCallItem,
    *,
    message: str,
    code: str,
    started_at: datetime,
) -> ToolCallItem:
    """Return a failed ToolCallItem whose error is visible to the model."""
    completed_at = datetime.now(UTC)
    return tool_call.model_copy(update={
        "status": ToolCallStatus.FAILED,
        "result": ToolCallResult(
            content=message,
            structured_content={
                "status": "error",
                "content": [{"text": message}],
            },
        ),
        "error": ToolCallError(message=message, code=code),
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_ms": _duration_ms(started_at, completed_at),
    })


def _result_text(value: Any) -> str:
    """Convert arbitrary tool output into model-visible tool text."""
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def _structured_result(value: Any) -> dict[str, Any] | None:
    """Return a JSON-compatible structured result when possible."""
    if isinstance(value, dict):
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    if isinstance(value, (list, tuple)):
        return {
            "value": json.loads(json.dumps(value, ensure_ascii=False, default=str)),
        }
    return None


def _duration_ms(started_at: datetime, completed_at: datetime) -> int:
    """Return elapsed milliseconds between tool start and completion."""
    return max(int((completed_at - started_at).total_seconds() * 1000), 0)
