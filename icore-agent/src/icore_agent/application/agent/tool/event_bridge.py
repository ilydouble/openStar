"""Strands callback and hook bridge for agent tool events."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent

from icore_agent.domain.chat.session import (
    ToolCallError,
    ToolCallItem,
    ToolCallResult,
    ToolCallStatus,
    ToolFunction,
)
from icore_agent.domain.chat.turn import TurnEvent

from .payloads import (
    json_dumps,
    json_safe_object,
    result_text,
    tool_arguments,
    tool_call_id,
    tool_name,
)


class StrandsToolEventBridge:
    """Convert Strands callbacks and tool hooks into turn-item events."""

    def __init__(self, *, session_id: str, turn_id: str) -> None:
        """Create a bridge for one turn."""
        self._session_id = session_id
        self._turn_id = turn_id
        self._emit: Callable[[TurnEvent], None] | None = None
        self._emit_assistant_delta: Callable[[str], None] | None = None
        self._started_at: dict[str, datetime] = {}
        self._items: dict[str, ToolCallItem] = {}

    @contextmanager
    def bound_to(
        self,
        *,
        emit: Callable[[TurnEvent], None],
        emit_assistant_delta: Callable[[str], None],
    ) -> Iterator[None]:
        """Bind synchronous event sinks for the duration of one Strands run."""
        previous = self._emit
        previous_delta = self._emit_assistant_delta
        self._emit = emit
        self._emit_assistant_delta = emit_assistant_delta
        try:
            yield
        finally:
            self._emit = previous
            self._emit_assistant_delta = previous_delta

    def register_hooks(self, registry, **kwargs: Any) -> None:
        """Register Strands lifecycle hooks."""
        _ = kwargs
        registry.add_callback(BeforeToolCallEvent, self.on_before_tool_call)
        registry.add_callback(AfterToolCallEvent, self.on_after_tool_call)

    def on_callback(self, **kwargs: Any) -> None:
        """Observe Strands streaming callbacks."""
        current_tool = kwargs.get("current_tool_use")
        if isinstance(current_tool, dict):
            self.record_start(current_tool)
        token = kwargs.get("data")
        if token and isinstance(token, str) and self._emit_assistant_delta is not None:
            self._emit_assistant_delta(token)

    def on_before_tool_call(self, event: BeforeToolCallEvent) -> None:
        """Observe a Strands before-tool-call event."""
        self.record_start(event.tool_use)

    def on_after_tool_call(self, event: AfterToolCallEvent) -> None:
        """Observe a Strands after-tool-call event."""
        self.record_finish(event.tool_use, event.result,
                           exception=event.exception)

    def record_start(self, tool_use: dict[str, Any]) -> None:
        """Emit a tool-call start item once per Strands tool-use id."""
        provider_tool_call_id = tool_call_id(tool_use)
        if not provider_tool_call_id or provider_tool_call_id in self._items:
            return
        arguments = tool_arguments(tool_use)
        started_at = datetime.now(UTC)
        item = ToolCallItem(
            provider_tool_call_id=provider_tool_call_id,
            function=ToolFunction(
                name=tool_name(tool_use),
                arguments_text=json_dumps(arguments),
                arguments_json=arguments,
            ),
            started_at=started_at,
            created_at=started_at,
        )
        self._items[provider_tool_call_id] = item
        self._started_at[provider_tool_call_id] = started_at
        self._emit_event(TurnEvent.item_started(
            session_id=self._session_id,
            turn_id=self._turn_id,
            item=item,
        ))

    def record_finish(
        self,
        tool_use: dict[str, Any],
        result: dict[str, Any],
        *,
        exception: Exception | None,
    ) -> None:
        """Emit a completed or failed tool-call item."""
        provider_tool_call_id = tool_call_id(tool_use)
        if not provider_tool_call_id:
            return
        if provider_tool_call_id not in self._items:
            self.record_start(tool_use)
        item = self._items.get(provider_tool_call_id)
        if item is None:
            return
        safe_result = json_safe_object(result)
        completed_at = datetime.now(UTC)
        status = str(safe_result.get("status") or (
            "error" if exception else "success"
        ))
        error_message = str(exception) if exception else None
        if status == "error" and not error_message:
            error_message = result_text(safe_result)
        completed = item.model_copy(update={
            "status": (
                ToolCallStatus.FAILED
                if exception is not None or status == "error"
                else ToolCallStatus.COMPLETED
            ),
            "result": ToolCallResult(
                content=result_text(safe_result),
                structured_content=safe_result,
            ),
            "error": (
                ToolCallError(
                    message=error_message or "Tool call failed",
                    code=type(exception).__name__ if exception else status,
                )
                if exception is not None or status == "error"
                else None
            ),
            "completed_at": completed_at,
            "duration_ms": self._duration_ms(provider_tool_call_id, completed_at),
        })
        self._items[provider_tool_call_id] = completed
        self._emit_event(TurnEvent.item_completed(
            session_id=self._session_id,
            turn_id=self._turn_id,
            item=completed,
        ))

    def _duration_ms(self, provider_tool_call_id: str, completed_at: datetime) -> int | None:
        started_at = self._started_at.get(provider_tool_call_id)
        if started_at is None:
            return None
        return max(int((completed_at - started_at).total_seconds() * 1000), 0)

    def _emit_event(self, event: TurnEvent) -> None:
        emit = self._emit
        if emit is None:
            return
        emit(event)
