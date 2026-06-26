"""Attachment references loaded for an agent turn."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AgentImageAttachment:
    """Image attachment reference passed from file assets into agent context."""

    filename: str
    ref: str
    file_uuid: str

    def to_context_payload(self) -> dict[str, Any]:
        """Return the compact dict shape used by prompt context assembly."""
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

    def to_context_payload(self) -> dict[str, Any]:
        """Return the compact dict shape used by prompt context assembly."""
        return {
            "filename": self.filename,
            "file_uuid": self.file_uuid,
        }
