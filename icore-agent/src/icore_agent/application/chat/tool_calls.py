"""Tool-call persistence hooks for Strands chat turns."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent

from icore_agent.shared.logging.app_logger import get_logger

if TYPE_CHECKING:
    from .services.history_service import ChatHistoryService

log = get_logger(__name__)


class ChatToolCallRecorder:
    """Persist Strands tool-call lifecycle events for one chat turn."""

    def __init__(
        self,
        *,
        chat_history: "ChatHistoryService",
        session_id: str,
        user_id: str,
    ) -> None:
        """Create a recorder scoped to one authenticated session turn."""
        self._chat_history = chat_history
        self._session_id = session_id
        self._user_id = user_id
        self._started_at: dict[str, datetime] = {}
        self._tool_names: dict[str, str] = {}
        self._tool_call_ids: list[str] = []

    @property
    def tool_call_ids(self) -> tuple[str, ...]:
        """Return tool call ids observed during the turn in first-seen order."""
        return tuple(self._tool_call_ids)

    def register_hooks(self, registry, **kwargs: Any) -> None:
        """Register Strands hook callbacks on the provided hook registry."""
        _ = kwargs
        registry.add_callback(BeforeToolCallEvent, self.on_before_tool_call)
        registry.add_callback(AfterToolCallEvent, self.on_after_tool_call)

    def on_before_tool_call(self, event: BeforeToolCallEvent) -> None:
        """Record a Strands before-tool-call event."""
        self.record_start(event.tool_use)

    def on_after_tool_call(self, event: AfterToolCallEvent) -> None:
        """Record a Strands after-tool-call event."""
        self.record_finish(event.tool_use, event.result,
                           exception=event.exception)

    def record_start(self, tool_use: dict[str, Any]) -> None:
        """Persist a tool call start from a Strands toolUse payload."""
        tool_call_id = self._tool_call_id(tool_use)
        if not tool_call_id:
            return
        tool_name = self._tool_name(tool_use)
        arguments = self._arguments(tool_use)
        if tool_call_id not in self._tool_call_ids:
            self._tool_call_ids.append(tool_call_id)
        self._started_at.setdefault(tool_call_id, datetime.now(UTC))
        self._tool_names[tool_call_id] = tool_name
        try:
            self._chat_history.start_tool_call(
                self._session_id,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                arguments=arguments,
            )
        except Exception as exc:
            log.warning(
                "tool_call_start_persist_failed",
                session_id=self._session_id,
                tool_call_id=tool_call_id,
                error=str(exc),
            )

    def record_finish(
        self,
        tool_use: dict[str, Any],
        result: dict[str, Any],
        *,
        exception: Exception | None,
    ) -> None:
        """Persist a tool call result and matching tool message content."""
        tool_call_id = self._tool_call_id(tool_use)
        if not tool_call_id:
            return
        if tool_call_id not in self._started_at:
            self.record_start(tool_use)

        safe_result = _json_safe_object(result)
        status = str(safe_result.get("status") or (
            "error" if exception else "success"
        ))
        error_code = type(exception).__name__ if exception else None
        error_message = str(exception) if exception else None
        if status == "error" and not error_message:
            error_message = _result_text(safe_result)
        elapsed_ms = self._elapsed_ms(tool_call_id)
        tool_message_id = self._save_tool_message(
            tool_call_id=tool_call_id,
            tool_name=self._tool_names.get(
                tool_call_id) or self._tool_name(tool_use),
            result=safe_result,
        )
        try:
            self._chat_history.finish_tool_call(
                self._session_id,
                tool_call_id=tool_call_id,
                status=status,
                result=safe_result,
                error_code=error_code,
                error_message=error_message,
                elapsed_ms=elapsed_ms,
                tool_message_id=tool_message_id,
            )
        except Exception as exc:
            log.warning(
                "tool_call_finish_persist_failed",
                session_id=self._session_id,
                tool_call_id=tool_call_id,
                error=str(exc),
            )

    def _save_tool_message(
        self,
        *,
        tool_call_id: str,
        tool_name: str,
        result: dict[str, Any],
    ) -> int | None:
        """Persist the tool result as a tool-role chat message."""
        try:
            return self._chat_history.save_tool_message(
                self._session_id,
                self._user_id,
                _json_dumps(result),
                metadata={
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                },
            )
        except Exception as exc:
            log.warning(
                "tool_message_persist_failed",
                session_id=self._session_id,
                tool_call_id=tool_call_id,
                error=str(exc),
            )
            return None

    def _elapsed_ms(self, tool_call_id: str) -> int | None:
        """Return elapsed milliseconds since the recorded start time."""
        started_at = self._started_at.get(tool_call_id)
        if started_at is None:
            return None
        return max(int((datetime.now(UTC) - started_at).total_seconds() * 1000), 0)

    @staticmethod
    def _tool_call_id(tool_use: dict[str, Any]) -> str:
        """Extract a stable Strands tool-use id."""
        return str(tool_use.get("toolUseId") or "").strip()

    @staticmethod
    def _tool_name(tool_use: dict[str, Any]) -> str:
        """Extract a Strands tool name."""
        return str(tool_use.get("name") or "unknown").strip() or "unknown"

    @staticmethod
    def _arguments(tool_use: dict[str, Any]) -> dict[str, Any]:
        """Extract JSON-safe tool arguments from a Strands toolUse payload."""
        raw_arguments = tool_use.get("input")
        if not isinstance(raw_arguments, dict):
            return {}
        return _json_safe_object(raw_arguments)


def _json_safe_object(value: Any) -> dict[str, Any]:
    """Return a JSON-compatible object, wrapped as a dict when needed."""
    normalized = json.loads(_json_dumps(value))
    if isinstance(normalized, dict):
        return normalized
    return {"value": normalized}


def _json_dumps(value: Any) -> str:
    """Serialize JSON content with stable separators for message content."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _result_text(result: dict[str, Any]) -> str | None:
    """Extract a text error message from a Strands ToolResult payload."""
    content = result.get("content")
    if not isinstance(content, list):
        return None
    for block in content:
        if isinstance(block, dict) and block.get("text"):
            return str(block["text"])
    return None
