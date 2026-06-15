"""Protocol ports for agent context assembly."""

from __future__ import annotations

from typing import Any, Protocol

from icore_agent.domain.files import FileAsset
from icore_agent.domain.memory import TurnMemoryContext

AgentHistoryMessage = dict[str, Any]


class ConversationMemory(Protocol):
    """Conversation cache operations used by agent context workflows."""

    async def get_context(
        self,
        session_id: str,
    ) -> tuple[str | None, list[AgentHistoryMessage]]:
        """Return a cached summary and recent messages."""
        ...

    async def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> bool:
        """Append one message to the cached conversation."""
        ...


class AgentSessionReader(Protocol):
    """Durable agent session operations needed by context assembly."""

    def load_messages(
        self,
        public_id: str,
        user_id: str,
    ) -> list[AgentHistoryMessage]:
        """Load persisted messages for one owned session."""
        ...


class FileContextReader(Protocol):
    """File operations needed to build agent context attachments."""

    def get_owned_asset(
        self,
        *,
        uploader_public_id: str,
        file_uuid: str,
    ) -> FileAsset:
        """Return one owned file asset."""
        ...

    def create_download_url(
        self,
        *,
        uploader_public_id: str,
        file_uuid: str,
    ) -> str:
        """Create a browser GET URL for an owned completed file asset."""
        ...


class UserMemoryPromptBuilder(Protocol):
    """Durable user memory operations needed for prompt construction."""

    def build_memory_prompt(
        self,
        user_id: str,
        turn: TurnMemoryContext,
    ) -> str | None:
        """Return the bounded user-memory prompt section for one turn."""
        ...
