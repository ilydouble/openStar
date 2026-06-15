"""Application results and events for chat turn workflows."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ChatStreamEventKind(str, Enum):
    """Event kinds emitted by chat turn streaming."""

    TOKEN = "token"
    STATUS = "status"
    ERROR = "error"
    DONE = "done"
    # Emitted when Pi Agent writes or edits a file inside the project sandbox.
    # Carries the full PendingChange record so the frontend can show an
    # Undo / Save All card with the affected path and change ID.
    FILE_CHANGED = "file_changed"


@dataclass(frozen=True, slots=True)
class ChatTurnResult:
    """Completed non-streaming chat turn result."""

    session_id: str
    reply: str


@dataclass(frozen=True, slots=True)
class ChatStreamEvent:
    """Typed application event emitted while a chat turn is streaming."""

    kind: ChatStreamEventKind
    text: str = ""
    message: str = ""
    tool: str = ""
    input_preview: str = ""
    step: int | None = None
    # Populated for FILE_CHANGED events: the full PendingChange dict from
    # pi-source-service (changeId, path, commitHash, tool, bytes, changedAt, savedAt).
    file_change: dict[str, Any] | None = None

    @classmethod
    def token(cls, text: str) -> "ChatStreamEvent":
        """Create a token delta event."""
        return cls(kind=ChatStreamEventKind.TOKEN, text=text)

    @classmethod
    def status(
        cls,
        *,
        step: int,
        tool: str,
        input_preview: str = "",
    ) -> "ChatStreamEvent":
        """Create a tool/status progress event."""
        return cls(
            kind=ChatStreamEventKind.STATUS,
            step=step,
            tool=tool,
            input_preview=input_preview,
        )

    @classmethod
    def error(cls, message: str) -> "ChatStreamEvent":
        """Create an error event."""
        return cls(kind=ChatStreamEventKind.ERROR, message=message)

    @classmethod
    def done(cls) -> "ChatStreamEvent":
        """Create a terminal done event."""
        return cls(kind=ChatStreamEventKind.DONE)

    @classmethod
    def file_changed(cls, change: dict[str, Any]) -> "ChatStreamEvent":
        """Create a file-changed event carrying the Pi Agent PendingChange record."""
        return cls(kind=ChatStreamEventKind.FILE_CHANGED, file_change=change)

    def to_payload(self) -> dict[str, Any]:
        """Return the JSON payload exposed by the HTTP streaming adapter."""
        payload: dict[str, Any] = {"type": self.kind.value}
        if self.kind is ChatStreamEventKind.TOKEN:
            payload["text"] = self.text
        elif self.kind is ChatStreamEventKind.STATUS:
            payload["step"] = int(self.step or 0)
            payload["tool"] = self.tool
            payload["input_preview"] = self.input_preview
        elif self.kind is ChatStreamEventKind.ERROR:
            payload["message"] = self.message
        elif self.kind is ChatStreamEventKind.FILE_CHANGED:
            payload["change"] = self.file_change or {}
        return payload
