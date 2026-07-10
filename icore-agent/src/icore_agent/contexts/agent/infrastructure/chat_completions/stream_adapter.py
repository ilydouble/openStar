"""Adapt LiteLLM Chat Completions responses to provider-neutral events."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from icore_agent.contexts.agent.domain.loop import (
    ModelReasoningDelta,
    ModelStepResult,
    ModelStreamEvent,
    ModelTextDelta,
    ModelToolCallCompleted,
)
from icore_agent.contexts.agent.domain.session import (
    AgentMessageItem,
    ReasoningItem,
    SessionItemStatus,
)

from .tool_call_assembler import ToolCallAssembler, ToolCallChunk


class LiteLLMStreamAdapter:
    """Convert one LiteLLM stream into provider-neutral model events."""

    def __init__(self, *, model_id: str, provider: str | None) -> None:
        """Create an adapter for one model sampling response."""
        self._model_id = model_id
        self._provider = provider
        self._content_parts: list[str] = []
        self._reasoning_parts: list[str] = []
        self._chunks: list[Any] = []
        self._usage: dict[str, int] | None = None
        self._finish_reason = ""
        self._response_id: str | None = None
        self._tool_calls = ToolCallAssembler()

    def consume(self, chunk: Any) -> list[ModelStreamEvent]:
        """Consume one LiteLLM chunk and return its neutral delta events."""
        self._chunks.append(chunk)
        self._response_id = self._response_id or response_id(chunk)
        chunk_usage = response_usage(chunk)
        if chunk_usage is not None:
            self._usage = chunk_usage

        choice = first_choice(chunk)
        if not choice:
            return []
        finish_reason = _get(choice, "finish_reason")
        if finish_reason:
            self._finish_reason = str(finish_reason)

        events: list[ModelStreamEvent] = []
        delta = _get(choice, "delta") or {}
        reasoning_delta = reasoning_content(delta)
        if reasoning_delta:
            self._reasoning_parts.append(reasoning_delta)
            events.append(ModelReasoningDelta(text=reasoning_delta))
        text_delta = message_content(delta)
        if text_delta:
            self._content_parts.append(text_delta)
            events.append(ModelTextDelta(text=text_delta))
        for raw_tool_call in tool_calls(delta):
            events.extend(self._tool_calls.consume(
                normalized_tool_call_chunk(raw_tool_call),
            ))
        return events

    def finalize(self) -> list[ModelStreamEvent]:
        """Finalize tool calls and append the single model step result."""
        tool_calls = self._tool_calls.finalize(
            finish_reason=self._finish_reason,
        )
        events: list[ModelStreamEvent] = [
            ModelToolCallCompleted(tool_call=tool_call)
            for tool_call in tool_calls
        ]
        events.append(ModelStepResult(
            assistant_item=AgentMessageItem(
                text="".join(self._content_parts),
                status=SessionItemStatus.COMPLETED,
            ),
            reasoning_item=reasoning_item("".join(self._reasoning_parts)),
            tool_calls=tool_calls,
            deltas=list(self._content_parts),
            usage=self._usage,
            model=self._model_id,
            provider=self._provider,
            stop_reason=(
                self._finish_reason
                or ("tool_calls" if tool_calls else "stop")
            ),
            raw_response_id=self._response_id,
            raw_payload=list(self._chunks),
        ))
        return events


def adapt_complete_response(
    response: Any,
    *,
    model_id: str,
    provider: str | None,
) -> list[ModelStreamEvent]:
    """Adapt a non-streaming LiteLLM response to the same event contract."""
    choice = first_choice(response)
    message = _get(choice, "message") or {}
    finish_reason = str(_get(choice, "finish_reason") or "")
    content = message_content(message)
    reasoning = reasoning_content(message)
    assembler = ToolCallAssembler()

    events: list[ModelStreamEvent] = []
    if reasoning:
        events.append(ModelReasoningDelta(text=reasoning))
    if content:
        events.append(ModelTextDelta(text=content))
    for fallback_index, raw_tool_call in enumerate(tool_calls(message)):
        events.extend(assembler.consume(normalized_tool_call_chunk(
            raw_tool_call,
            fallback_index=fallback_index,
        )))
    assembled_tool_calls = assembler.finalize(finish_reason=finish_reason)
    events.extend(
        ModelToolCallCompleted(tool_call=tool_call)
        for tool_call in assembled_tool_calls
    )
    events.append(ModelStepResult(
        assistant_item=AgentMessageItem(
            text=content,
            status=SessionItemStatus.COMPLETED,
        ),
        reasoning_item=reasoning_item(reasoning),
        tool_calls=assembled_tool_calls,
        deltas=[content] if content else [],
        usage=response_usage(response),
        model=model_id,
        provider=provider,
        stop_reason=(
            finish_reason
            or ("tool_calls" if assembled_tool_calls else "stop")
        ),
        raw_response_id=response_id(response),
        raw_payload=response,
    ))
    return events


def is_stream_response(response: Any) -> bool:
    """Return whether a LiteLLM response is a streaming iterator."""
    if _get(response, "choices") is not None:
        return False
    return hasattr(response, "__aiter__") or hasattr(response, "__iter__")


async def iter_stream_chunks(response: Any) -> AsyncIterator[Any]:
    """Yield chunks from either an async or synchronous LiteLLM stream."""
    if hasattr(response, "__aiter__"):
        async for chunk in response:
            yield chunk
        return
    for chunk in response:
        yield chunk


def first_choice(response: Any) -> Any:
    """Extract the first choice from a LiteLLM response or chunk."""
    choices = _get(response, "choices") or []
    if not choices:
        return {}
    return choices[0]


def message_content(message: Any) -> str:
    """Extract plain assistant content from a message or delta."""
    content = _get(message, "content")
    return str(content) if content is not None else ""


def reasoning_content(message: Any) -> str:
    """Extract reasoning from a normalized LiteLLM message or delta."""
    content = _get(message, "reasoning_content")
    if content is None:
        content = _get(message, "reasoning")
    return str(content) if content is not None else ""


def tool_calls(message: Any) -> list[Any]:
    """Extract tool calls from a normalized LiteLLM message or delta."""
    calls = _get(message, "tool_calls") or []
    return list(calls)


def normalized_tool_call_chunk(
    raw_tool_call: Any,
    *,
    fallback_index: int = 0,
) -> ToolCallChunk:
    """Normalize one OpenAI-compatible LiteLLM tool-call fragment."""
    raw_index = _get(raw_tool_call, "index")
    index = fallback_index if raw_index is None else int(raw_index)
    function = _get(raw_tool_call, "function") or {}
    raw_arguments = _get(function, "arguments")
    if raw_arguments is None:
        arguments_delta = None
    elif isinstance(raw_arguments, str):
        arguments_delta = raw_arguments
    else:
        arguments_delta = json.dumps(raw_arguments, ensure_ascii=False)
    provider_tool_call_id = _get(raw_tool_call, "id")
    call_type = _get(raw_tool_call, "type")
    name = _get(function, "name")
    return ToolCallChunk(
        index=index,
        provider_tool_call_id=(
            str(provider_tool_call_id) if provider_tool_call_id else None
        ),
        call_type=str(call_type) if call_type else None,
        name=str(name) if name else None,
        arguments_delta=arguments_delta,
    )


def reasoning_item(content: str) -> ReasoningItem | None:
    """Build a completed reasoning item when content is non-empty."""
    if not content.strip():
        return None
    return ReasoningItem(
        text=content,
        status=SessionItemStatus.COMPLETED,
    )


def response_usage(response: Any) -> dict[str, int] | None:
    """Extract normalized usage counts from a LiteLLM response."""
    raw_usage = _get(response, "usage")
    if raw_usage is None:
        return None
    prompt_tokens = int(_get(raw_usage, "prompt_tokens") or 0)
    completion_tokens = int(_get(raw_usage, "completion_tokens") or 0)
    total_tokens = int(_get(raw_usage, "total_tokens") or 0)
    if total_tokens <= 0:
        total_tokens = prompt_tokens + completion_tokens
    if total_tokens <= 0:
        return None
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


def response_id(response: Any) -> str | None:
    """Return the provider response identifier when available."""
    value = _get(response, "id")
    return str(value) if value else None


def _get(value: Any, key: str) -> Any:
    """Read a field from a mapping-like object or an attribute object."""
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)
