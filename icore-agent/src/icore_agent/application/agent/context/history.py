"""Conversation history loading for agent context assembly."""

from __future__ import annotations

from typing import Any

from icore_agent.domain.agent import ChatCompletionRole
from icore_agent.shared.logging.app_logger import get_logger

from .ports import AgentHistoryMessage, AgentSessionReader, ConversationMemory

log = get_logger(__name__)


async def load_history_context(
    *,
    session_id: str,
    user_id: str,
    incognito: bool,
    conversation_memory: ConversationMemory,
    agent_session: AgentSessionReader,
) -> tuple[str | None, list[AgentHistoryMessage]]:
    """Load cached history with a durable-history fallback when allowed."""
    summary, history = await conversation_memory.get_context(session_id)
    if not history and not incognito:
        try:
            history = agent_session.load_messages(session_id, user_id)
        except (PermissionError, LookupError):
            history = []
    return summary or None, history


def to_strands_messages(history: list[AgentHistoryMessage]) -> list[dict[str, Any]]:
    """Convert cached or persisted messages to Strands message format."""
    return [
        {
            "role": message["role"],
            "content": [
                {"type": "text", "text": message["content"]}
            ],
        }
        for message in history
        if message.get("role") in (
            ChatCompletionRole.USER.value,
            ChatCompletionRole.ASSISTANT.value,
        )
        and message.get("content")
    ]
