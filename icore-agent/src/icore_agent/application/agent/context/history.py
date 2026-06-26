"""Conversation history loading for agent context assembly."""

from __future__ import annotations

from icore_agent.domain.agent import ChatCompletionRole
from icore_agent.domain.agent.prompt import PromptHistoryItem
from domain.agent.session import (
    AgentMessageItem,
    SessionItemStatus,
    UserInput,
    UserInputType,
    UserMessageItem,
)
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
    current_user_message: str = "",
) -> tuple[str | None, list[AgentHistoryMessage]]:
    """Load cached history with a durable-history fallback when allowed."""
    summary, history = await conversation_memory.get_context(session_id)
    if not history and not incognito:
        try:
            history = agent_session.load_messages(session_id, user_id)
            history = exclude_current_user_message(
                history,
                current_user_message,
            )
        except (PermissionError, LookupError):
            history = []
    return summary or None, history


def to_model_visible_items(
    history: list[AgentHistoryMessage],
) -> list[PromptHistoryItem]:
    """Convert loaded history into provider-neutral model-visible items."""
    items: list[PromptHistoryItem] = []
    for message in history:
        content = str(message.get("content") or "")
        if not content:
            continue
        role = message.get("role")
        if role == ChatCompletionRole.USER.value:
            items.append(UserMessageItem(content=[
                UserInput(type=UserInputType.TEXT, text=content),
            ]))
        elif role == ChatCompletionRole.ASSISTANT.value:
            items.append(AgentMessageItem(
                status=SessionItemStatus.COMPLETED,
                text=content,
            ))
    return items


def exclude_current_user_message(
    history: list[AgentHistoryMessage],
    current_user_message: str,
) -> list[AgentHistoryMessage]:
    """Remove the already-persisted current user message from fallback history."""
    normalized = current_user_message.strip()
    if not normalized:
        return history
    for index in range(len(history) - 1, -1, -1):
        message = history[index]
        if (
            message.get("role") == ChatCompletionRole.USER.value
            and str(message.get("content") or "").strip() == normalized
        ):
            return [*history[:index], *history[index + 1:]]
    return history
