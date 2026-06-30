"""Helpers for resolving session payloads used by memory extraction."""

from __future__ import annotations

from typing import Any

from icore_agent.application.agent.session import AgentSessionService
from icore_agent.infrastructure.memory.conversation import ConversationMemory


async def resolve_session_extract_context(
    session_id: str,
    *,
    user_id: str,
    conversation_memory: ConversationMemory,
    agent_session: AgentSessionService,
) -> tuple[str, list[dict[str, str]]]:
    """Return the best available summary and messages for one session extract."""
    summary, redis_messages = await conversation_memory.get_context(session_id)
    summary_text = str(summary or "").strip()
    normalized_redis = _normalize_messages(redis_messages)
    if summary_text or normalized_redis:
        return summary_text, normalized_redis

    try:
        persisted = agent_session.load_messages(session_id, user_id)
    except (LookupError, PermissionError):
        persisted = []
    return summary_text, _normalize_messages(persisted)


def _normalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Keep only role/content fields expected by the memory extract pipeline."""
    normalized: list[dict[str, str]] = []
    for message in messages:
        role = str(message.get("role") or "").strip().lower()
        content = str(message.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        normalized.append({"role": role, "content": content})
    return normalized
