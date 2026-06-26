"""Application-level context manager for one agent turn."""

from __future__ import annotations

from dataclasses import dataclass

from icore_agent.domain.agent.context import (
    AgentFileAttachment,
    AgentImageAttachment,
)
from icore_agent.domain.agent.prompt import PromptHistoryItem
from icore_agent.domain.agent.session import ContextItem


@dataclass(frozen=True, slots=True)
class AgentContext:
    """Loaded runtime materials used to assemble an agent prompt envelope."""

    summary: str | None
    history_items: list[PromptHistoryItem]
    has_rag: bool
    image_attachments: list[AgentImageAttachment]
    file_attachments: list[AgentFileAttachment]
    user_memory_prompt: str | None = None

    @classmethod
    def empty(cls) -> AgentContext:
        """Return an empty context after context loading fails."""
        return cls(
            summary=None,
            history_items=[],
            has_rag=False,
            image_attachments=[],
            file_attachments=[],
            user_memory_prompt=None,
        )

    @property
    def has_attachments(self) -> bool:
        """Return whether file or RAG context is present."""
        return bool(
            self.has_rag
            or self.image_attachments
            or self.file_attachments
        )

    def to_context_items(self) -> list[ContextItem]:
        """Build model-visible runtime context items for PromptEnvelope."""
        items: list[ContextItem] = []
        if self.summary:
            items.append(ContextItem(
                kind="session_summary",
                content=f"Earlier conversation summary:\n{self.summary}",
            ))
        if self.user_memory_prompt:
            items.append(ContextItem(
                kind="user_memory",
                content=self.user_memory_prompt,
            ))
        items.extend(
            attachment.to_context_item()
            for attachment in self.image_attachments
        )
        items.extend(
            attachment.to_context_item()
            for attachment in self.file_attachments
        )
        return items
