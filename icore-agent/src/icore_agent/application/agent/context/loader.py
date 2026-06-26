"""Top-level agent context loader."""

from __future__ import annotations

from icore_agent.shared.logging.app_logger import get_logger

from .agent_context import AgentContext
from .attachments import load_attachment_context
from .history import load_history_context, to_model_visible_items
from .memory import build_user_memory_prompt
from .ports import (
    AgentSessionReader,
    ConversationMemory,
    FileContextReader,
    UserMemoryPromptBuilder,
)

log = get_logger(__name__)


async def load_agent_context(
    *,
    session_id: str,
    file_uuids: tuple[str, ...],
    user_id: str,
    user_message: str = "",
    incognito: bool = False,
    file_service: FileContextReader,
    agent_session: AgentSessionReader,
    conversation_memory: ConversationMemory,
    user_memory_service: UserMemoryPromptBuilder | None = None,
) -> AgentContext:
    """Load cached history, durable history fallback, files, and memory prompt."""
    try:
        summary, history = await load_history_context(
            session_id=session_id,
            user_id=user_id,
            incognito=incognito,
            conversation_memory=conversation_memory,
            agent_session=agent_session,
            current_user_message=user_message,
        )
    except Exception as exc:
        log.warning("load_context_fallback",
                    session_id=session_id, error=str(exc))
        return AgentContext.empty()

    image_refs, file_refs = load_attachment_context(
        file_uuids=file_uuids,
        user_id=user_id,
        file_service=file_service,
    )
    user_memory_prompt = build_user_memory_prompt(
        user_id=user_id,
        user_message=user_message,
        session_summary=summary,
        incognito=incognito,
        user_memory_service=user_memory_service,
    )
    return AgentContext(
        summary=summary,
        history_items=to_model_visible_items(history),
        has_rag=False,
        image_attachments=image_refs,
        file_attachments=file_refs,
        user_memory_prompt=user_memory_prompt,
    )
