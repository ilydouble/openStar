"""Direct LiteLLM Chat Completions runner for prompt envelopes."""

from __future__ import annotations

import asyncio
import inspect
import json
from typing import Any

import litellm

from icore_agent.application.agent.tool import ToolDefinition, ToolExecutionContext
from icore_agent.domain.agent import ChatCompletionRole
from icore_agent.config import settings
from icore_agent.domain.agent.prompt import PromptEnvelope

from .renderer import (
    render_chat_completions_messages,
    render_chat_completions_tool_choice,
    render_chat_completions_tools,
)

_MAX_TOOL_ROUNDS = 8


class ChatCompletionsRunner:
    """Prepared runner that executes PromptEnvelope through LiteLLM chat completions."""

    def __init__(
        self,
        *,
        model_id: str,
        client_args: dict[str, Any],
        params: dict[str, Any],
        tool_definitions: list[ToolDefinition],
        tool_bridge: Any | None = None,
        callback_handler: Any | None = None,
        max_tool_rounds: int = _MAX_TOOL_ROUNDS,
    ) -> None:
        """Create a runner with resolved provider config and executable tools."""
        self._model_id = model_id
        self._client_args = dict(client_args)
        self._params = dict(params)
        self._tool_definitions = {
            definition.name: definition for definition in tool_definitions
        }
        self._tool_bridge = tool_bridge
        self._callback_handler = callback_handler
        self._max_tool_rounds = max_tool_rounds

    def __call__(self, prompt_envelope: PromptEnvelope) -> str:
        """Run one prompt envelope until the model returns a final answer."""
        messages = render_chat_completions_messages(prompt_envelope)
        tools = render_chat_completions_tools(prompt_envelope)
        tool_choice = render_chat_completions_tool_choice(prompt_envelope)

        for round_index in range(self._max_tool_rounds + 1):
            response = litellm.completion(
                model=self._model_id,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                **self._client_args,
                **self._params,
            )
            message = _first_message(response)
            content = _message_content(message)
            tool_calls = _message_tool_calls(message)
            if not tool_calls:
                if content and self._callback_handler is not None:
                    self._callback_handler(data=content)
                return content
            if round_index >= self._max_tool_rounds:
                raise RuntimeError("Chat Completions tool loop exceeded limit")
            messages.append(_assistant_tool_call_message(message, tool_calls))
            for tool_call in tool_calls:
                messages.append(self._execute_tool_call(tool_call))
            tool_choice = "auto"
        raise RuntimeError("Chat Completions tool loop ended without a reply")

    def _execute_tool_call(self, tool_call: Any) -> dict[str, Any]:
        """Execute one model-requested tool call and return a tool role message."""
        tool_call_id = _tool_call_id(tool_call)
        name = _tool_call_name(tool_call)
        arguments = _tool_call_arguments(tool_call)
        tool_use = {
            "toolUseId": tool_call_id,
            "name": name,
            "input": arguments,
        }
        self._record_start(tool_use)
        definition = self._tool_definitions.get(name)
        exception: Exception | None = None
        if definition is None:
            exception = LookupError(f"Unknown tool: {name}")
            text = str(exception)
        else:
            try:
                result = definition.execute(
                    tool_call_id,
                    arguments,
                    ToolExecutionContext(tool_call_id=tool_call_id),
                )
                if inspect.isawaitable(result):
                    result = asyncio.run(result)
                text = _result_text(result)
            except Exception as exc:
                exception = exc
                text = str(exc)
        result_payload = {
            "toolUseId": tool_call_id,
            "status": "error" if exception else "success",
            "content": [{"text": text}],
        }
        self._record_finish(tool_use, result_payload, exception=exception)
        return {
            "role": ChatCompletionRole.TOOL.value,
            "tool_call_id": tool_call_id,
            "name": name,
            "content": text,
        }

    def _record_start(self, tool_use: dict[str, Any]) -> None:
        """Forward a tool start to the bound tool bridge when available."""
        if self._tool_bridge is not None and hasattr(self._tool_bridge, "record_start"):
            self._tool_bridge.record_start(tool_use)

    def _record_finish(
        self,
        tool_use: dict[str, Any],
        result: dict[str, Any],
        *,
        exception: Exception | None,
    ) -> None:
        """Forward a tool finish to the bound tool bridge when available."""
        if self._tool_bridge is not None and hasattr(self._tool_bridge, "record_finish"):
            self._tool_bridge.record_finish(
                tool_use,
                result,
                exception=exception,
            )


def create_chat_completions_runner(
    *,
    callback_handler=None,
    session_id: str = "",
    hooks: list[Any] | None = None,
    user_id: str = "",
    prompt_envelope: PromptEnvelope | None = None,
    tool_definitions: list[ToolDefinition] | None = None,
    **_: Any,
) -> ChatCompletionsRunner:
    """Create a LiteLLM Chat Completions runner for one agent turn."""
    _ = prompt_envelope
    selected_model = settings.effective_model_id()
    resolved = settings.resolve_litellm_config(
        model_id=selected_model,
        user_id=user_id,
        session_id=session_id,
        max_tokens=settings.agent_max_tokens,
        temperature=settings.agent_temperature,
    )
    tool_bridge = _first_tool_bridge(hooks or [])
    return ChatCompletionsRunner(
        model_id=resolved.model_id,
        client_args=resolved.client_args,
        params=resolved.params,
        tool_definitions=list(tool_definitions or []),
        tool_bridge=tool_bridge,
        callback_handler=callback_handler,
    )


def _first_tool_bridge(hooks: list[Any]) -> Any | None:
    """Return the first hook that exposes direct tool event methods."""
    for hook in hooks:
        if hasattr(hook, "record_start") and hasattr(hook, "record_finish"):
            return hook
    return None


def _first_message(response: Any) -> Any:
    """Extract the first assistant message from a LiteLLM response."""
    choices = _get(response, "choices") or []
    first = choices[0]
    return _get(first, "message") or {}


def _message_content(message: Any) -> str:
    """Extract plain assistant content from a message object or dict."""
    return str(_get(message, "content") or "")


def _message_tool_calls(message: Any) -> list[Any]:
    """Extract tool calls from a message object or dict."""
    calls = _get(message, "tool_calls") or []
    return list(calls)


def _assistant_tool_call_message(
    message: Any,
    tool_calls: list[Any],
) -> dict[str, Any]:
    """Render the assistant message that requested tool calls."""
    return {
        "role": ChatCompletionRole.ASSISTANT.value,
        "content": _message_content(message) or None,
        "tool_calls": [_normalize_tool_call(call) for call in tool_calls],
    }


def _normalize_tool_call(tool_call: Any) -> dict[str, Any]:
    """Normalize provider tool-call objects for the next Chat Completions round."""
    return {
        "id": _tool_call_id(tool_call),
        "type": "function",
        "function": {
            "name": _tool_call_name(tool_call),
            "arguments": _tool_call_arguments_text(tool_call),
        },
    }


def _tool_call_id(tool_call: Any) -> str:
    """Extract a stable tool-call id."""
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


def _tool_call_arguments(tool_call: Any) -> dict[str, Any]:
    """Parse model-supplied function-call arguments into a dict."""
    raw = _tool_call_arguments_text(tool_call)
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    if isinstance(parsed, dict):
        return parsed
    return {}


def _result_text(value: Any) -> str:
    """Convert arbitrary tool output into tool-message text."""
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _get(value: Any, key: str) -> Any:
    """Read a field from either a mapping-like object or an attribute object."""
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)
