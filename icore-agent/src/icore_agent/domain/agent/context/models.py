"""Data models for agent context assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AgentImageAttachment:
    """Image attachment reference passed from file assets into agent context."""

    filename: str
    ref: str
    file_uuid: str

    def to_orchestrator_payload(self) -> dict[str, Any]:
        """Return the dict shape consumed by the engine orchestrator."""
        return {
            "filename": self.filename,
            "ref": self.ref,
            "file_uuid": self.file_uuid,
        }


@dataclass(frozen=True, slots=True)
class AgentFileAttachment:
    """Non-image file attachment reference passed into agent context."""

    filename: str
    file_uuid: str

    def to_agent_payload(self) -> dict[str, Any]:
        """Return the compact dict shape sent to the agent turn boundary."""
        return {
            "filename": self.filename,
            "file_uuid": self.file_uuid,
        }


@dataclass(frozen=True, slots=True)
class AgentContext:
    """Loaded prompt context for one agent turn."""

    summary: str | None
    runner_history: list[dict[str, Any]]
    has_rag: bool
    image_attachments: list[AgentImageAttachment]
    file_attachments: list[AgentFileAttachment]
    user_memory_prompt: str | None = None

    @classmethod
    def empty(cls) -> AgentContext:
        """Return an empty context after a cache loading failure."""
        return cls(
            summary=None,
            runner_history=[],
            has_rag=False,
            image_attachments=[],
            file_attachments=[],
            user_memory_prompt=None,
        )

    @property
    def has_attachments(self) -> bool:
        """Return whether file or RAG context should enable tools."""
        return bool(
            self.has_rag
            or self.image_attachments
            or self.file_attachments
        )

    @property
    def image_attachment_payloads(self) -> list[dict[str, Any]]:
        """Return image attachments in the engine orchestrator dict shape."""
        return [
            attachment.to_orchestrator_payload()
            for attachment in self.image_attachments
        ]

    @property
    def file_attachment_payloads(self) -> list[dict[str, Any]]:
        """Return non-image file attachments in the compact agent dict shape."""
        return [
            attachment.to_agent_payload()
            for attachment in self.file_attachments
        ]
