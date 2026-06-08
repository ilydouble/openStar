"""Application results and turn-stream events for chat workflows."""

from __future__ import annotations

from dataclasses import dataclass

from icore_agent.domain.chat.turn import TurnEvent, TurnEventKind

ChatStreamEvent = TurnEvent
ChatStreamEventKind = TurnEventKind


@dataclass(frozen=True, slots=True)
class ChatTurnResult:
    """Completed non-streaming chat turn result."""

    session_id: str
    reply: str
    turn_id: str | None = None
