"""Tests for provider-specific Chat Completions request policy."""

from __future__ import annotations

from icore_agent.contexts.agent.infrastructure.chat_completions.request_policy import (
    build_chat_completions_request,
)


def test_zai_tool_stream_merges_with_existing_extra_body() -> None:
    """Supported Z.AI models should stream tools without losing thinking config."""
    params = {
        "extra_body": {
            "thinking": {
                "type": "enabled",
                "clear_thinking": True,
            },
            "custom": "value",
        },
    }

    request = build_chat_completions_request(
        model_id="zai/glm-5.1",
        messages=[{"role": "user", "content": "Compare values"}],
        tools=[{"type": "function", "function": {"name": "compare"}}],
        tool_choice="auto",
        client_args={"api_key": "secret"},
        params=params,
    )

    assert request["stream"] is True
    assert request["extra_body"] == {
        "thinking": {
            "type": "enabled",
            "clear_thinking": True,
        },
        "custom": "value",
        "tool_stream": True,
    }
    assert params["extra_body"].get("tool_stream") is None


def test_tool_stream_is_limited_to_supported_zai_tool_requests() -> None:
    """Provider-only flags should not leak into unrelated requests."""
    common = {
        "messages": [{"role": "user", "content": "Hello"}],
        "tool_choice": "auto",
        "client_args": {},
        "params": {},
    }

    openai = build_chat_completions_request(
        model_id="openai/gpt-4o-mini",
        tools=[{"type": "function"}],
        **common,
    )
    unsupported_zai = build_chat_completions_request(
        model_id="zai/glm-4-plus",
        tools=[{"type": "function"}],
        **common,
    )
    no_tools = build_chat_completions_request(
        model_id="zai/glm-5.1",
        tools=[],
        **common,
    )

    assert "extra_body" not in openai
    assert "extra_body" not in unsupported_zai
    assert "extra_body" not in no_tools
