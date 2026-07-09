"""Conversation transcript side effects for completed agent turns."""

from __future__ import annotations

from typing import Any

from icore_agent.contexts.agent.domain import ChatCompletionRole
from icore_agent.shared.logging.app_logger import get_logger

log = get_logger(__name__)


class TurnTranscriptRecorder:
    """Record completed turn transcript and durable memory extraction."""

    def __init__(
        self,
        *,
        agent_session: Any,
        conversation_memory: Any,
        user_memory_service: Any | None = None,
    ) -> None:
        """Create a transcript recorder for completed turn side effects."""
        self._agent_session = agent_session
        self._conversation_memory = conversation_memory
        self._user_memory_service = user_memory_service

    async def append_memory_pair(self, command: Any, reply: str) -> bool:
        """Append completed turn messages to the conversation cache."""
        compressed_user = await self._conversation_memory.append_message(
            command.session_id,
            ChatCompletionRole.USER.value,
            command.message,
        )
        compressed_assistant = await self._conversation_memory.append_message(
            command.session_id,
            ChatCompletionRole.ASSISTANT.value,
            reply,
        )
        return compressed_user or compressed_assistant

    async def maybe_extract_user_memory(
        self,
        command: Any,
        session_compressed: bool,
    ) -> None:
        """Run durable memory extraction when Redis compression rolls older turns."""
        if command.incognito:
            return
        if self._user_memory_service is None:
            log.warning(
                "user_memory_extract_skipped",
                user_id=command.user_id,
                session_id=command.session_id,
                reason="service_not_wired",
            )
            return
        if not self._user_memory_service.should_extract_on_compression(
            session_compressed=session_compressed,
        ):
            return
        try:
            log.info(
                "user_memory_extract_scheduled",
                user_id=command.user_id,
                session_id=command.session_id,
                reason="session_compressed",
                session_compressed=session_compressed,
            )
            summary, messages = await self._conversation_memory.get_context(
                command.session_id,
            )
            await self._user_memory_service.extract_from_session(
                user_id=command.user_id,
                session_id=command.session_id,
                session_summary=summary,
                recent_messages=messages,
            )
        except Exception as exc:
            log.warning(
                "user_memory_extract_schedule_failed",
                user_id=command.user_id,
                session_id=command.session_id,
                error=str(exc),
            )
