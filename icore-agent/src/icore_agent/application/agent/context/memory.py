"""Durable memory prompt loading for agent context assembly."""

from __future__ import annotations

from icore_agent.domain.memory import TurnMemoryContext

from .ports import UserMemoryPromptBuilder


def build_user_memory_prompt(
    *,
    user_id: str,
    user_message: str,
    session_summary: str | None,
    incognito: bool,
    user_memory_service: UserMemoryPromptBuilder | None,
) -> str | None:
    """Build durable user memory prompt context when enabled for the turn."""
    if incognito or user_memory_service is None:
        return None
    return user_memory_service.build_memory_prompt(
        user_id,
        TurnMemoryContext(
            message=user_message,
            session_summary=session_summary or None,
        ),
    )
