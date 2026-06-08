"""Compatibility projection from turn tool items to legacy tool-call rows."""

from __future__ import annotations

from typing import Any

from icore_agent.domain.chat.session import ToolCallItem, ToolCallStatus
from icore_agent.domain.chat.turn import TurnEvent, TurnEventKind
from icore_agent.shared.logging.app_logger import get_logger

from .payloads import json_dumps

log = get_logger(__name__)


class TurnToolProjection:
    """Project one turn's ToolCallItem events into existing tool-call storage."""

    def __init__(self, chat_history: Any) -> None:
        """Create a per-turn projection scope."""
        self._chat_history = chat_history
        self._tool_call_ids: list[str] = []

    @property
    def tool_call_ids(self) -> tuple[str, ...]:
        """Return observed provider tool-call ids in first-seen order."""
        return tuple(self._tool_call_ids)

    def persist_event(self, command: Any, event: TurnEvent) -> None:
        """Persist a tool item event to legacy compatibility tables."""
        item = event.item
        if command.incognito or not isinstance(item, ToolCallItem):
            return
        tool_call_id = item.provider_tool_call_id or item.id
        if tool_call_id not in self._tool_call_ids:
            self._tool_call_ids.append(tool_call_id)
        if event.kind is TurnEventKind.ITEM_STARTED:
            self._persist_started(command, tool_call_id, item)
            return
        if event.kind is TurnEventKind.ITEM_COMPLETED:
            self._persist_completed(command, tool_call_id, item)

    def attach_to_assistant(
        self,
        command: Any,
        *,
        assistant_message_id: int | None,
    ) -> None:
        """Link observed tool calls to the completed assistant message."""
        if assistant_message_id is None or not self._tool_call_ids:
            return
        try:
            self._chat_history.attach_tool_calls_to_assistant(
                command.session_id,
                tool_call_ids=tuple(self._tool_call_ids),
                assistant_message_id=assistant_message_id,
            )
        except (PermissionError, LookupError) as exc:
            log.warning(
                "assistant_tool_call_link_failed",
                session_id=command.session_id,
                error=str(exc),
            )

    def _persist_started(
        self,
        command: Any,
        tool_call_id: str,
        item: ToolCallItem,
    ) -> None:
        """Persist legacy tool-call start state."""
        try:
            self._chat_history.start_tool_call(
                command.session_id,
                tool_call_id=tool_call_id,
                tool_name=item.function.name or "unknown",
                arguments=item.function.arguments_json or {},
            )
        except (PermissionError, LookupError) as exc:
            log.warning(
                "tool_call_start_persist_failed",
                session_id=command.session_id,
                tool_call_id=tool_call_id,
                error=str(exc),
            )

    def _persist_completed(
        self,
        command: Any,
        tool_call_id: str,
        item: ToolCallItem,
    ) -> None:
        """Persist legacy tool-call final state and matching tool message."""
        tool_message_id = self._save_tool_message(command, item, tool_call_id)
        try:
            self._chat_history.finish_tool_call(
                command.session_id,
                tool_call_id=tool_call_id,
                status=(
                    "error"
                    if _value(item.status) == ToolCallStatus.FAILED.value
                    else "success"
                ),
                result=(
                    item.result.structured_content
                    if item.result is not None
                    else None
                ),
                error_code=item.error.code if item.error is not None else None,
                error_message=item.error.message if item.error is not None else None,
                elapsed_ms=item.duration_ms,
                tool_message_id=tool_message_id,
            )
        except (PermissionError, LookupError) as exc:
            log.warning(
                "tool_call_finish_persist_failed",
                session_id=command.session_id,
                tool_call_id=tool_call_id,
                error=str(exc),
            )

    def _save_tool_message(
        self,
        command: Any,
        item: ToolCallItem,
        tool_call_id: str,
    ) -> int | None:
        """Persist a tool result message for compatibility history."""
        result = item.result.structured_content if item.result is not None else {}
        try:
            return self._chat_history.save_tool_message(
                command.session_id,
                command.user_id,
                json_dumps(result),
                metadata={
                    "tool_call_id": tool_call_id,
                    "tool_name": item.function.name or "unknown",
                },
            )
        except (AttributeError, PermissionError, LookupError) as exc:
            log.warning(
                "tool_message_persist_failed",
                session_id=command.session_id,
                tool_call_id=tool_call_id,
                error=str(exc),
            )
            return None


def _value(value: Any) -> str:
    """Return the plain value for enum-like objects."""
    return str(getattr(value, "value", value))
