"""Provider-specific request policy for LiteLLM Chat Completions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_ZAI_STREAMING_TOOL_MODELS = frozenset({
    "glm-4.6",
    "glm-4.7",
    "glm-5",
    "glm-5-turbo",
    "glm-5.1",
    "glm-5.2",
})


def build_chat_completions_request(
    *,
    model_id: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_choice: Any,
    client_args: Mapping[str, Any],
    params: Mapping[str, Any],
) -> dict[str, Any]:
    """Build one streaming LiteLLM request with provider-specific features."""
    request = {
        "model": model_id,
        "messages": messages,
        "tools": tools,
        "tool_choice": tool_choice,
        **dict(client_args),
        **dict(params),
        "stream": True,
    }
    if tools and _supports_zai_streaming_tools(model_id):
        request["extra_body"] = _extra_body_with_tool_stream(
            request.get("extra_body"),
        )
    return request


def _supports_zai_streaming_tools(model_id: str) -> bool:
    """Return whether the selected Z.AI model accepts tool_stream."""
    provider, separator, model_name = model_id.lower().partition("/")
    return (
        bool(separator)
        and provider == "zai"
        and model_name in _ZAI_STREAMING_TOOL_MODELS
    )


def _extra_body_with_tool_stream(value: Any) -> dict[str, Any]:
    """Merge the Z.AI tool-stream flag into an existing extra body."""
    if value is None:
        extra_body: dict[str, Any] = {}
    elif isinstance(value, Mapping):
        extra_body = dict(value)
    else:
        raise TypeError("LiteLLM extra_body must be a mapping")
    extra_body["tool_stream"] = True
    return extra_body
