"""Helpers for attributing LiteLLM usage callbacks to authenticated users."""

from __future__ import annotations

from collections.abc import Mapping
from contextvars import ContextVar, Token
from typing import Any

from icore_agent.shared.runtime.user_context import current_runtime_user

_turn_usage_events: ContextVar[list[dict[str, Any]] | None] = ContextVar(
    "turn_usage_events",
    default=None,
)


def begin_turn_usage_capture() -> Token:
    """Start buffering LiteLLM usage events for one chat turn."""
    return _turn_usage_events.set([])


def end_turn_usage_capture(reset_token: Token) -> None:
    """Stop buffering LiteLLM usage events for the active chat turn."""
    _turn_usage_events.reset(reset_token)


def active_turn_usage_events() -> list[dict[str, Any]] | None:
    """Return the in-flight usage buffer for the active chat turn, if any."""
    return _turn_usage_events.get()


def resolve_litellm_user_id(kwargs: Mapping[str, Any]) -> str | None:
    """Resolve the billing user id from LiteLLM kwargs metadata or runtime context."""
    metadata = kwargs.get("metadata")
    if isinstance(metadata, dict):
        user_id = str(metadata.get("user_id") or "").strip()
        if user_id:
            return user_id
    user = current_runtime_user()
    if user is None:
        return None
    return user.public_id


def resolve_litellm_session_id(kwargs: Mapping[str, Any]) -> str:
    """Resolve the chat session id from LiteLLM kwargs metadata when present."""
    metadata = kwargs.get("metadata")
    if isinstance(metadata, dict):
        return str(metadata.get("session_id") or "").strip()
    return ""


def _normalize_usage_counts(raw_usage: Any) -> dict[str, int] | None:
    """Normalize LiteLLM usage payloads into integer token counters."""
    if raw_usage is None:
        return None
    if isinstance(raw_usage, Mapping):
        prompt_tokens = int(raw_usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(raw_usage.get("completion_tokens", 0) or 0)
        total_tokens = int(raw_usage.get("total_tokens", 0) or 0)
    else:
        prompt_tokens = int(getattr(raw_usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(raw_usage, "completion_tokens", 0) or 0)
        total_tokens = int(getattr(raw_usage, "total_tokens", 0) or 0)
    if total_tokens <= 0:
        total_tokens = prompt_tokens + completion_tokens
    if total_tokens <= 0:
        return None
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


def _completion_text(completion_response: Any) -> str:
    """Extract assistant text from a LiteLLM completion response."""
    choices = getattr(completion_response, "choices", None)
    if not choices and isinstance(completion_response, Mapping):
        choices = completion_response.get("choices")
    if not choices:
        return ""
    first = choices[0]
    message = getattr(first, "message", None)
    if message is None and isinstance(first, Mapping):
        message = first.get("message")
    if message is None:
        content = getattr(first, "text", None)
        return str(content or "")
    content = getattr(message, "content", None)
    if content is None and isinstance(message, Mapping):
        content = message.get("content")
    return str(content or "")


def _estimate_usage_from_payload(
    kwargs: Mapping[str, Any],
    completion_response: Any,
) -> dict[str, int] | None:
    """Estimate token usage when providers omit usage metadata on the response."""
    model = str(kwargs.get("model") or "unknown")
    messages = kwargs.get("messages")
    completion_text = _completion_text(completion_response)
    if not messages and not completion_text:
        return None
    try:
        from litellm import token_counter
    except Exception:
        return None
    prompt_tokens = 0
    if messages:
        try:
            prompt_tokens = int(token_counter(model=model, messages=messages) or 0)
        except Exception:
            prompt_tokens = 0
    completion_tokens = 0
    if completion_text:
        try:
            completion_tokens = int(token_counter(model=model, text=completion_text) or 0)
        except Exception:
            completion_tokens = max(len(completion_text) // 4, 1)
    total_tokens = prompt_tokens + completion_tokens
    if total_tokens <= 0:
        return None
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


def extract_litellm_usage(
    kwargs: Mapping[str, Any],
    completion_response: Any,
) -> dict[str, int] | None:
    """Extract token usage from a LiteLLM response, with a token_counter fallback."""
    raw_usage = getattr(completion_response, "usage", None)
    if raw_usage is None and isinstance(completion_response, Mapping):
        raw_usage = completion_response.get("usage")
    if raw_usage is None:
        hidden = getattr(completion_response, "_hidden_params", None)
        if isinstance(hidden, Mapping):
            raw_usage = hidden.get("usage")
    normalized = _normalize_usage_counts(raw_usage)
    if normalized is not None:
        return normalized
    return _estimate_usage_from_payload(kwargs, completion_response)


def build_litellm_usage_event(
    kwargs: Mapping[str, Any],
    completion_response: Any,
) -> dict[str, Any] | None:
    """Build one usage event payload from a LiteLLM success callback."""
    usage_metrics = extract_litellm_usage(kwargs, completion_response)
    if usage_metrics is None:
        return None
    return {
        "session_id": resolve_litellm_session_id(kwargs),
        "model": str(kwargs.get("model") or "unknown"),
        **usage_metrics,
    }


def buffer_litellm_usage_event(event: Mapping[str, Any]) -> bool:
    """Append one usage event to the active chat-turn buffer when present."""
    bucket = active_turn_usage_events()
    if bucket is None:
        return False
    bucket.append(dict(event))
    return True


def flush_turn_usage_capture(
    *,
    user_id: str,
    session_id: str,
    record_usage,
) -> int:
    """Persist all buffered LiteLLM usage events for one chat turn."""
    bucket = active_turn_usage_events()
    if not bucket:
        return 0
    recorded = 0
    for event in list(bucket):
        total_tokens = int(event.get("total_tokens", 0) or 0)
        if total_tokens <= 0:
            continue
        record_usage(
            user_id=user_id,
            session_id=session_id or str(event.get("session_id") or ""),
            model=str(event.get("model") or "unknown"),
            prompt_tokens=int(event.get("prompt_tokens", 0) or 0),
            completion_tokens=int(event.get("completion_tokens", 0) or 0),
            total_tokens=total_tokens,
        )
        recorded += 1
    bucket.clear()
    return recorded
