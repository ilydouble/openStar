"""Direct LiteLLM Chat Completions model client for prompt envelopes."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import litellm

from icore_agent.config import settings
from icore_agent.contexts.agent.domain.loop import (
    ModelReasoningDelta,
    ModelStepResult,
    ModelStreamEvent,
    ModelTextDelta,
    ModelToolCallCompleted,
    ModelToolCallDelta,
    ModelToolCallStarted,
)
from icore_agent.contexts.agent.domain.prompt import PromptEnvelope
from icore_agent.contexts.agent.domain.session import (
    AgentMessageItem,
    ReasoningItem,
    SessionItemStatus,
    ToolCallItem,
    ToolCallStatus,
    ToolFunction,
)

from .renderer import (
    render_chat_completions_messages,
    render_chat_completions_tool_choice,
    render_chat_completions_tools,
)


class ChatCompletionsModelClient:
    """Model client that performs one LiteLLM Chat Completions sampling step."""

    def __init__(
        self,
        *,
        model_id: str,
        client_args: dict[str, Any],
        params: dict[str, Any],
    ) -> None:
        """Create a model client with resolved provider config."""
        self._model_id = model_id
        self._client_args = dict(client_args)
        self._params = dict(params)
        self._provider = _provider_from_model(model_id)

    async def sample(self, envelope: PromptEnvelope) -> ModelStepResult:
        """Call LiteLLM once and return provider-neutral assistant/tool items."""
        deltas: list[str] = []
        reasoning_parts: list[str] = []
        result: ModelStepResult | None = None
        async for event in self.stream(envelope):
            if isinstance(event, ModelTextDelta):
                deltas.append(event.text)
            elif isinstance(event, ModelReasoningDelta):
                reasoning_parts.append(event.text)
            elif isinstance(event, ModelStepResult):
                result = event
        if result is None:
            return ModelStepResult(
                assistant_item=AgentMessageItem(
                    text="".join(deltas),
                    status=SessionItemStatus.COMPLETED,
                ),
                reasoning_item=_reasoning_item("".join(reasoning_parts)),
                deltas=deltas,
                model=self._model_id,
                provider=self._provider,
                stop_reason="stop",
            )
        return _model_step_result_copy(result, deltas=deltas)

    async def stream(
        self,
        envelope: PromptEnvelope,
    ) -> AsyncIterator[ModelStreamEvent]:
        """Call LiteLLM once and yield provider-neutral streaming events."""
        kwargs = {
            "model": self._model_id,
            "messages": render_chat_completions_messages(envelope),
            "tools": render_chat_completions_tools(envelope),
            "tool_choice": render_chat_completions_tool_choice(envelope),
            **self._client_args,
            **self._params,
        }
        kwargs["stream"] = True
        response = await litellm.acompletion(**kwargs)
        if _is_stream_response(response):
            async for event in _stream_step_events(
                response,
                model_id=self._model_id,
                provider=self._provider,
            ):
                yield event
            return
        yield _response_step_result(
            response,
            model_id=self._model_id,
            provider=self._provider,
        )


def create_chat_completions_model_client(
    *,
    session_id: str = "",
    user_id: str = "",
    **_: Any,
) -> ChatCompletionsModelClient:
    """Create a LiteLLM Chat Completions model client for one agent turn."""
    selected_model = settings.effective_model_id()
    resolved = settings.resolve_litellm_config(
        model_id=selected_model,
        user_id=user_id,
        session_id=session_id,
        max_tokens=settings.agent_max_tokens,
        temperature=settings.agent_temperature,
    )
    return ChatCompletionsModelClient(
        model_id=resolved.model_id,
        client_args=resolved.client_args,
        params=resolved.params,
    )


def _first_message(response: Any) -> Any:
    """Extract the first assistant message from a LiteLLM response."""
    choices = _get(response, "choices") or []
    if not choices:
        return {}
    first = choices[0]
    return _get(first, "message") or {}


def _response_step_result(
    response: Any,
    *,
    model_id: str,
    provider: str | None,
) -> ModelStepResult:
    """Convert one full provider response into a model step result."""
    message = _first_message(response)
    content = _message_content(message)
    tool_calls = [_tool_call_item(call)
                  for call in _message_tool_calls(message)]
    return ModelStepResult(
        assistant_item=AgentMessageItem(
            text=content,
            status=SessionItemStatus.COMPLETED,
        ),
        reasoning_item=_reasoning_item(_message_reasoning_content(message)),
        tool_calls=tool_calls,
        usage=_response_usage(response),
        model=model_id,
        provider=provider,
        stop_reason=_stop_reason(response, tool_calls),
        raw_response_id=_response_id(response),
        raw_payload=response,
    )


def _is_stream_response(response: Any) -> bool:
    """Return whether a LiteLLM response is a streaming iterator."""
    if _get(response, "choices") is not None:
        return False
    return hasattr(response, "__aiter__") or hasattr(response, "__iter__")


async def _stream_step_events(
    response: Any,
    *,
    model_id: str,
    provider: str | None,
) -> AsyncIterator[ModelStreamEvent]:
    """Yield text/reasoning deltas while collecting a final model result."""
    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    chunks: list[Any] = []
    usage: dict[str, int] | None = None
    finish_reason = ""
    response_id: str | None = None
    tool_call_states: dict[int, dict[str, Any]] = {}

    async for chunk in _iter_stream_chunks(response):
        chunks.append(chunk)
        response_id = response_id or _response_id(chunk)
        chunk_usage = _response_usage(chunk)
        if chunk_usage is not None:
            usage = chunk_usage
        choice = _first_choice(chunk)
        if not choice:
            continue
        reason = _get(choice, "finish_reason")
        if reason:
            finish_reason = str(reason)
        delta = _get(choice, "delta") or {}
        reasoning_delta = _delta_reasoning_content(delta)
        if reasoning_delta:
            reasoning_parts.append(reasoning_delta)
            yield ModelReasoningDelta(text=reasoning_delta)
        text_delta = _delta_content(delta)
        if text_delta:
            content_parts.append(text_delta)
            yield ModelTextDelta(text=text_delta)
        for raw_tool_delta in _delta_tool_calls(delta):
            index = int(_get(raw_tool_delta, "index") or 0)
            is_new = index not in tool_call_states
            _merge_tool_call_deltas(tool_call_states, [raw_tool_delta])
            state = tool_call_states[index]
            item_id = _tool_call_item_id(state, index)
            state["item_id"] = item_id
            function = _get(raw_tool_delta, "function") or {}
            arguments_delta = _get(function, "arguments")
            if is_new:
                yield ModelToolCallStarted(
                    item_id=item_id,
                    provider_tool_call_id=_tool_call_id(state),
                    index=index,
                    name=_tool_call_name(state),
                )
            if arguments_delta is not None:
                yield ModelToolCallDelta(
                    item_id=item_id,
                    provider_tool_call_id=_tool_call_id(state),
                    index=index,
                    name=_tool_call_name(state),
                    arguments_delta=str(arguments_delta),
                )

    content = "".join(content_parts)
    tool_calls = [
        _tool_call_item(state, item_id=str(state.get("item_id") or ""))
        for _index, state in sorted(tool_call_states.items())
        if _tool_call_has_content(state)
    ]
    for tool_call in tool_calls:
        yield ModelToolCallCompleted(
            tool_call=tool_call.model_copy(update={
                "status": ToolCallStatus.READY,
            }),
        )
    yield ModelStepResult(
        assistant_item=AgentMessageItem(
            text=content,
            status=SessionItemStatus.COMPLETED,
        ),
        reasoning_item=_reasoning_item("".join(reasoning_parts)),
        tool_calls=tool_calls,
        deltas=content_parts,
        usage=usage,
        model=model_id,
        provider=provider,
        stop_reason=finish_reason or ("tool_calls" if tool_calls else "stop"),
        raw_response_id=response_id,
        raw_payload=chunks,
    )


def _model_step_result_copy(
    result: ModelStepResult,
    *,
    deltas: list[str],
) -> ModelStepResult:
    """Return a model step result with collected compatibility deltas."""
    return ModelStepResult(
        assistant_item=result.assistant_item,
        reasoning_item=result.reasoning_item,
        tool_calls=result.tool_calls,
        deltas=deltas,
        usage=result.usage,
        model=result.model,
        provider=result.provider,
        stop_reason=result.stop_reason,
        raw_response_id=result.raw_response_id,
        raw_payload=result.raw_payload,
    )


async def _iter_stream_chunks(response: Any) -> AsyncIterator[Any]:
    """Yield chunks from either an async or sync LiteLLM stream."""
    if hasattr(response, "__aiter__"):
        async for chunk in response:
            yield chunk
        return
    for chunk in response:
        yield chunk


def _first_choice(response: Any) -> Any:
    """Extract the first choice from a response chunk or full response."""
    choices = _get(response, "choices") or []
    if not choices:
        return {}
    return choices[0]


def _delta_content(delta: Any) -> str:
    """Extract one streamed assistant text delta."""
    content = _get(delta, "content")
    return str(content) if content is not None else ""


def _delta_reasoning_content(delta: Any) -> str:
    """Extract one streamed model reasoning delta."""
    content = _get(delta, "reasoning_content")
    if content is None:
        content = _get(delta, "reasoning")
    return str(content) if content is not None else ""


def _delta_tool_calls(delta: Any) -> list[Any]:
    """Extract streamed tool-call deltas from one response chunk."""
    calls = _get(delta, "tool_calls") or []
    return list(calls)


def _merge_tool_call_deltas(
    states: dict[int, dict[str, Any]],
    deltas: list[Any],
) -> None:
    """Merge OpenAI-style streamed tool-call deltas by tool-call index."""
    for raw in deltas:
        index = int(_get(raw, "index") or 0)
        state = states.setdefault(
            index,
            {
                "index": index,
                "id": "",
                "type": "function",
                "function": {"name": "", "arguments": ""},
            },
        )
        call_id = _get(raw, "id")
        if call_id:
            state["id"] = str(call_id)
        call_type = _get(raw, "type")
        if call_type:
            state["type"] = str(call_type)
        function = _get(raw, "function") or {}
        name = _get(function, "name")
        if name:
            state["function"]["name"] = str(name)
        arguments = _get(function, "arguments")
        if arguments is not None:
            state["function"]["arguments"] += str(arguments)


def _tool_call_has_content(tool_call: Any) -> bool:
    """Return whether a streamed tool-call state contains useful data."""
    function = _get(tool_call, "function") or {}
    return bool(
        _get(tool_call, "id")
        or _get(function, "name")
        or _get(function, "arguments")
    )


def _message_content(message: Any) -> str:
    """Extract plain assistant content from a message object or dict."""
    return str(_get(message, "content") or "")


def _message_reasoning_content(message: Any) -> str:
    """Extract model reasoning from a full assistant message."""
    content = _get(message, "reasoning_content")
    if content is None:
        content = _get(message, "reasoning")
    return str(content) if content is not None else ""


def _reasoning_item(content: str) -> ReasoningItem | None:
    """Build a completed reasoning item when the provider returned content."""
    if not content.strip():
        return None
    return ReasoningItem(
        text=content,
        status=SessionItemStatus.COMPLETED,
    )


def _message_tool_calls(message: Any) -> list[Any]:
    """Extract tool calls from a message object or dict."""
    calls = _get(message, "tool_calls") or []
    return list(calls)


def _tool_call_item(tool_call: Any, *, item_id: str | None = None) -> ToolCallItem:
    """Convert one provider tool call into a domain ToolCallItem."""
    arguments_text = _tool_call_arguments_text(tool_call)
    function = ToolFunction(
        name=_tool_call_name(tool_call),
        arguments_text=arguments_text,
        arguments_json=_tool_call_arguments(arguments_text),
    )
    if item_id:
        return ToolCallItem(
            id=item_id,
            provider_tool_call_id=_tool_call_id(tool_call),
            index=_tool_call_index(tool_call),
            function=function,
        )
    return ToolCallItem(
        provider_tool_call_id=_tool_call_id(tool_call),
        index=_tool_call_index(tool_call),
        function=function,
    )


def _tool_call_id(tool_call: Any) -> str:
    """Extract a stable provider tool-call id."""
    return str(_get(tool_call, "id") or "")


def _tool_call_item_id(tool_call: Any, index: int) -> str:
    """Return a stable domain item id for a streamed provider tool call."""
    return str(_get(tool_call, "item_id") or _tool_call_id(tool_call) or f"tool-call-{index}")


def _tool_call_index(tool_call: Any) -> int | None:
    """Extract the provider tool-call index when available."""
    value = _get(tool_call, "index")
    if value is None:
        return None
    return int(value)


def _tool_call_name(tool_call: Any) -> str:
    """Extract the requested function name."""
    function = _get(tool_call, "function") or {}
    return str(_get(function, "name") or "")


def _tool_call_arguments_text(tool_call: Any) -> str:
    """Extract raw function-call arguments text."""
    function = _get(tool_call, "function") or {}
    raw = _get(function, "arguments")
    if isinstance(raw, str):
        return raw
    return json.dumps(raw or {}, ensure_ascii=False)


def _tool_call_arguments(raw: str) -> dict[str, Any]:
    """Parse model-supplied function-call arguments into a dict."""
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    if isinstance(parsed, dict):
        return parsed
    return {}


def _response_usage(response: Any) -> dict[str, int] | None:
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


def _stop_reason(response: Any, tool_calls: list[ToolCallItem]) -> str:
    """Return the provider finish reason or infer a tool-call stop."""
    choices = _get(response, "choices") or []
    if choices:
        reason = _get(choices[0], "finish_reason")
        if reason:
            return str(reason)
    if tool_calls:
        return "tool_calls"
    return "stop"


def _response_id(response: Any) -> str | None:
    """Return the provider response id when one is available."""
    value = _get(response, "id")
    return str(value) if value else None


def _provider_from_model(model: str | None) -> str | None:
    """Infer a provider label from LiteLLM-style model ids."""
    value = str(model or "").strip()
    if not value or "/" not in value:
        return None
    provider, _separator, _model_name = value.partition("/")
    return provider or None


def _get(value: Any, key: str) -> Any:
    """Read a field from either a mapping-like object or an attribute object."""
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)
