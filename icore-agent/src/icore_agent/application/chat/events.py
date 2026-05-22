"""Application results and events for chat turn workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ChatStreamEventKind = Literal["token", "status", "error", "done"]


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

    @classmethod
    def token(cls, text: str) -> "ChatStreamEvent":
        """Create a token delta event."""
        return cls(kind="token", text=text)

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
            kind="status",
            step=step,
            tool=tool,
            input_preview=input_preview,
        )

    @classmethod
    def error(cls, message: str) -> "ChatStreamEvent":
        """Create an error event."""
        return cls(kind="error", message=message)

    @classmethod
    def done(cls) -> "ChatStreamEvent":
        """Create a terminal done event."""
        return cls(kind="done")

    def to_payload(self) -> dict[str, Any]:
        """Return the JSON payload exposed by the HTTP streaming adapter."""
        payload: dict[str, Any] = {"type": self.kind}
        if self.kind == "token":
            payload["text"] = self.text
        elif self.kind == "status":
            payload["step"] = int(self.step or 0)
            payload["tool"] = self.tool
            payload["input_preview"] = self.input_preview
        elif self.kind == "error":
            payload["message"] = self.message
        return payload
