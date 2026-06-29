"""Direct LiteLLM Chat Completions model client for prompt envelopes."""

from __future__ import annotations

import json
from typing import Any

import litellm

from icore_agent.application.agent.loop import ModelStepResult
from icore_agent.config import settings
from icore_agent.domain.agent.prompt import PromptEnvelope
from icore_agent.domain.agent.session import (
    AgentMessageItem,
    SessionItemStatus,
    ToolCallItem,
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
        kwargs = {
            "model": self._model_id,
            "messages": render_chat_completions_messages(envelope),
            "tools": render_chat_completions_tools(envelope),
            "tool_choice": render_chat_completions_tool_choice(envelope),
            **self._client_args,
            **self._params,
        }
        response = await litellm.acompletion(**kwargs)
        message = _first_message(response)
        content = _message_content(message)
        tool_calls = [_tool_call_item(call)
                      for call in _message_tool_calls(message)]
        return ModelStepResult(
            assistant_item=AgentMessageItem(
                text=content,
                status=SessionItemStatus.COMPLETED,
            ),
            tool_calls=tool_calls,
            usage=_response_usage(response),
            model=self._model_id,
            provider=self._provider,
            stop_reason=_stop_reason(response, tool_calls),
            raw_response_id=_response_id(response),
            raw_payload=response,
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


def _message_content(message: Any) -> str:
    """Extract plain assistant content from a message object or dict."""
    return str(_get(message, "content") or "")


def _message_tool_calls(message: Any) -> list[Any]:
    """Extract tool calls from a message object or dict."""
    calls = _get(message, "tool_calls") or []
    return list(calls)


def _tool_call_item(tool_call: Any) -> ToolCallItem:
    """Convert one provider tool call into a domain ToolCallItem."""
    arguments_text = _tool_call_arguments_text(tool_call)
    return ToolCallItem(
        provider_tool_call_id=_tool_call_id(tool_call),
        function=ToolFunction(
            name=_tool_call_name(tool_call),
            arguments_text=arguments_text,
            arguments_json=_tool_call_arguments(arguments_text),
        ),
    )


def _tool_call_id(tool_call: Any) -> str:
    """Extract a stable provider tool-call id."""
    return str(_get(tool_call, "id") or "")


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
