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
class AgentDataColumn:
    """Column preview metadata for one uploaded data file."""

    name: str
    dtype: str

    def to_orchestrator_payload(self) -> dict[str, str]:
        """Return the dict shape consumed by the engine orchestrator."""
        return {"name": self.name, "dtype": self.dtype}


@dataclass(frozen=True, slots=True)
class AgentDataAttachment:
    """Structured data attachment reference passed into agent context."""

    filename: str
    file_uuid: str
    abs_path: str
    columns: tuple[AgentDataColumn, ...] = ()
    row_count: int | None = None
    preview_md: str = ""
    preview_error: str = ""

    def to_orchestrator_payload(self) -> dict[str, Any]:
        """Return the dict shape consumed by the engine orchestrator."""
        return {
            "filename": self.filename,
            "file_uuid": self.file_uuid,
            "abs_path": self.abs_path,
            "columns": [
                column.to_orchestrator_payload()
                for column in self.columns
            ],
            "row_count": self.row_count,
            "preview_md": self.preview_md,
            "preview_error": self.preview_error,
        }


@dataclass(frozen=True, slots=True)
class AgentContext:
    """Loaded prompt context for one agent turn."""

    summary: str | None
    strands_history: list[dict[str, Any]]
    attachments_text: str | None
    has_rag: bool
    image_attachments: list[AgentImageAttachment]
    data_attachments: list[AgentDataAttachment]
    user_memory_prompt: str | None = None

    @classmethod
    def empty(cls) -> AgentContext:
        """Return an empty context after a cache loading failure."""
        return cls(
            summary=None,
            strands_history=[],
            attachments_text=None,
            has_rag=False,
            image_attachments=[],
            data_attachments=[],
            user_memory_prompt=None,
        )

    @property
    def has_attachments(self) -> bool:
        """Return whether file or RAG context should enable tools."""
        return bool(
            self.has_rag
            or self.image_attachments
            or self.data_attachments
        )

    @property
    def image_attachment_payloads(self) -> list[dict[str, Any]]:
        """Return image attachments in the engine orchestrator dict shape."""
        return [
            attachment.to_orchestrator_payload()
            for attachment in self.image_attachments
        ]

    @property
    def data_attachment_payloads(self) -> list[dict[str, Any]]:
        """Return data attachments in the engine orchestrator dict shape."""
        return [
            attachment.to_orchestrator_payload()
            for attachment in self.data_attachments
        ]
