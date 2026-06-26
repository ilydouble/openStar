"""Loaded context materials for one agent turn."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from icore_agent.domain.agent.prompt import ModelVisibleItem

from .attachments import AgentFileAttachment, AgentImageAttachment


@dataclass(frozen=True, slots=True)
class AgentContext:
    """Loaded context materials before prompt-envelope assembly."""

    summary: str | None
    history_items: list[ModelVisibleItem]
    has_rag: bool
    image_attachments: list[AgentImageAttachment]
    file_attachments: list[AgentFileAttachment]
    user_memory_prompt: str | None = None

    @classmethod
    def empty(cls) -> AgentContext:
        """Return an empty context after a cache loading failure."""
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

    @property
    def image_attachment_payloads(self) -> list[dict[str, Any]]:
        """Return image attachments in a compact dict shape."""
        return [
            attachment.to_context_payload()
            for attachment in self.image_attachments
        ]

    @property
    def file_attachment_payloads(self) -> list[dict[str, Any]]:
        """Return non-image file attachments in a compact dict shape."""
        return [
            attachment.to_context_payload()
            for attachment in self.file_attachments
        ]
