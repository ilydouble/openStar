"""Assemble provider-neutral tool calls from streamed argument fragments."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from icore_agent.contexts.agent.domain.loop import (
    ModelToolCallDelta,
    ModelToolCallStarted,
)
from icore_agent.contexts.agent.domain.session import (
    ToolCallError,
    ToolCallItem,
    ToolCallResult,
    ToolCallStatus,
    ToolFunction,
)
from icore_agent.shared.identifiers import uuid7
from icore_agent.shared.time.utils import utc_now

_INTERRUPTED_FINISH_REASONS = frozenset({
    "aborted",
    "content_filter",
    "error",
    "length",
})


@dataclass(frozen=True, slots=True)
class ToolCallChunk:
    """Normalized fields from one LiteLLM tool-call delta."""

    index: int
    provider_tool_call_id: str | None = None
    call_type: str | None = None
    name: str | None = None
    arguments_delta: str | None = None


@dataclass(slots=True)
class _ToolCallState:
    """Mutable assembly state for one provider tool-call index."""

    index: int
    item_id: str = field(default_factory=lambda: str(uuid7()))
    provider_tool_call_id: str | None = None
    call_type: str = "function"
    name: str | None = None
    argument_parts: list[str] = field(default_factory=list)

    @property
    def arguments_text(self) -> str:
        """Return all argument fragments in provider order."""
        return "".join(self.argument_parts)


class ToolCallAssembler:
    """Accumulate streamed tool calls and validate them before execution."""

    def __init__(self) -> None:
        """Create an empty per-response tool-call state collection."""
        self._states: dict[int, _ToolCallState] = {}

    def consume(
        self,
        chunk: ToolCallChunk,
    ) -> list[ModelToolCallStarted | ModelToolCallDelta]:
        """Merge one chunk and return the resulting provider-neutral events."""
        state = self._states.get(chunk.index)
        is_new = state is None
        if state is None:
            state = _ToolCallState(index=chunk.index)
            self._states[chunk.index] = state

        metadata_changed = self._merge_metadata(state, chunk)
        if chunk.arguments_delta:
            state.argument_parts.append(chunk.arguments_delta)

        events: list[ModelToolCallStarted | ModelToolCallDelta] = []
        if is_new:
            events.append(ModelToolCallStarted(
                item_id=state.item_id,
                provider_tool_call_id=state.provider_tool_call_id,
                index=state.index,
                name=state.name,
            ))
        if chunk.arguments_delta or (metadata_changed and not is_new):
            events.append(ModelToolCallDelta(
                item_id=state.item_id,
                provider_tool_call_id=state.provider_tool_call_id,
                index=state.index,
                name=state.name,
                arguments_delta=chunk.arguments_delta or "",
            ))
        return events

    def finalize(self, *, finish_reason: str) -> list[ToolCallItem]:
        """Return READY or FAILED tool calls after strict argument validation."""
        return [
            self._finalize_state(state, finish_reason=finish_reason)
            for _index, state in sorted(self._states.items())
        ]

    @staticmethod
    def _merge_metadata(
        state: _ToolCallState,
        chunk: ToolCallChunk,
    ) -> bool:
        """Merge late provider metadata and report whether it changed."""
        changed = False
        if (
            chunk.provider_tool_call_id
            and chunk.provider_tool_call_id != state.provider_tool_call_id
        ):
            state.provider_tool_call_id = chunk.provider_tool_call_id
            changed = True
        if chunk.call_type and chunk.call_type != state.call_type:
            state.call_type = chunk.call_type
            changed = True
        if chunk.name and chunk.name != state.name:
            state.name = chunk.name
            changed = True
        return changed

    @staticmethod
    def _finalize_state(
        state: _ToolCallState,
        *,
        finish_reason: str,
    ) -> ToolCallItem:
        """Validate one complete state and construct its terminal item."""
        arguments_text = state.arguments_text
        error_message = _argument_error(
            arguments_text,
            finish_reason=finish_reason,
        )
        arguments_json = None
        if error_message is None:
            parsed = json.loads(arguments_text)
            assert isinstance(parsed, dict)
            arguments_json = parsed

        function = ToolFunction(
            name=state.name,
            arguments_text=arguments_text,
            arguments_json=arguments_json,
        )
        if error_message is None:
            return ToolCallItem(
                id=state.item_id,
                provider_tool_call_id=state.provider_tool_call_id,
                index=state.index,
                function=function,
                status=ToolCallStatus.READY,
            )
        return ToolCallItem(
            id=state.item_id,
            provider_tool_call_id=state.provider_tool_call_id,
            index=state.index,
            function=function,
            status=ToolCallStatus.FAILED,
            result=ToolCallResult(
                content=error_message,
                structured_content={
                    "status": "error",
                    "content": [{"text": error_message}],
                },
            ),
            error=ToolCallError(
                message=error_message,
                code="InvalidToolArguments",
            ),
            completed_at=utc_now(),
        )


def _argument_error(raw: str, *, finish_reason: str) -> str | None:
    """Return a model-visible validation error for unsafe tool arguments."""
    normalized_reason = finish_reason.strip().lower()
    if normalized_reason in _INTERRUPTED_FINISH_REASONS:
        return (
            "Tool call arguments were incomplete because model generation "
            f"stopped with '{normalized_reason}'. Return a new tool call with "
            "one complete JSON object."
        )
    if not raw.strip():
        return (
            "Tool call arguments were empty. Return a new tool call with one "
            "complete JSON object."
        )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return (
            "Tool call arguments were not valid JSON. Return a new tool call "
            "with one complete JSON object."
        )
    if not isinstance(parsed, dict):
        return (
            "Tool call arguments must be a JSON object. Return a new tool call "
            "with an object as its arguments."
        )
    return None
