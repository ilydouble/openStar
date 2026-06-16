"""Top-level agent context loader."""

from __future__ import annotations

from icore_agent.shared.logging.app_logger import get_logger

from .attachments import load_attachment_context
from .history import load_history_context, to_runner_messages
from .memory import build_user_memory_prompt
from icore_agent.domain.agent.context.models import AgentContext
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
        runner_history=to_runner_messages(history),
        has_rag=False,
        image_attachments=image_refs,
        file_attachments=file_refs,
        user_memory_prompt=user_memory_prompt,
    )
