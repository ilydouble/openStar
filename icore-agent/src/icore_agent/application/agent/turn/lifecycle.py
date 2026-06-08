"""Turn lifecycle state transitions for agent execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from icore_agent.shared.time.utils import start_to_completed_duration_ms

from icore_agent.domain.chat.session import (
    AgentMessageItem,
    UserInput,
    UserInputType,
    UserMessageItem,
)
from icore_agent.domain.chat.turn import (
    Turn,
    TurnError,
    TurnEvent,
    TurnEventKind,
    TurnStatus,
)


@dataclass(frozen=True, slots=True)
class TurnCompletion:
    """Final event and metadata for a completed or failed turn."""

    event: TurnEvent
    status: TurnStatus
    error: TurnError | None
    completed_at: datetime
    duration_ms: int


@dataclass(slots=True)
class TurnLifecycle:
    """Own in-memory lifecycle state for one agent turn."""

    turn: Turn
    started_at: datetime
    reply: str = ""

    @classmethod
    def start(
        cls,
        *,
        session_id: str,
        started_at: datetime | None = None,
    ) -> TurnLifecycle:
        """Create a new in-progress turn lifecycle."""
        started = started_at or datetime.now(UTC)
        return cls(
            turn=Turn(session_id=session_id, started_at=started),
            started_at=started,
        )

    def started_event(self) -> TurnEvent:
        """Return the event that exposes the turn id."""
        return TurnEvent.turn_started(
            session_id=self.turn.session_id,
            turn_id=self.turn.id,
        )

    def user_message_event(self, message: str) -> TurnEvent:
        """Create and record the user-message item for this turn."""
        item = UserMessageItem(
            content=[
                UserInput(
                    type=UserInputType.TEXT,
                    text=message,
                )
            ],
            created_at=self.started_at,
            completed_at=self.started_at,
        )
        self.turn.upsert_item(item)
        return TurnEvent.item_completed(
            session_id=self.turn.session_id,
            turn_id=self.turn.id,
            item=item,
        )

    def apply_agent_event(self, event: TurnEvent) -> None:
        """Apply an item event emitted during the agent turn."""
        if event.item is not None:
            self.turn.upsert_item(event.item)
        if event.kind is TurnEventKind.ITEM_DELTA and event.delta:
            self.reply += str(event.delta.get("text") or "")
        elif (
            event.kind is TurnEventKind.ITEM_COMPLETED
            and isinstance(event.item, AgentMessageItem)
        ):
            self.reply = event.item.text

    def completed(
        self,
        *,
        completed_at: datetime | None = None,
    ) -> TurnCompletion:
        """Mark the turn completed and return final lifecycle metadata."""
        completed = completed_at or datetime.now(UTC)
        duration_ms = start_to_completed_duration_ms(self.started_at, completed)
        self.turn.status = TurnStatus.COMPLETED
        self.turn.error = None
        self.turn.completed_at = completed
        self.turn.duration_ms = duration_ms
        return TurnCompletion(
            event=TurnEvent.turn_completed(
                session_id=self.turn.session_id,
                turn_id=self.turn.id,
                reply=self.reply,
            ),
            status=TurnStatus.COMPLETED,
            error=None,
            completed_at=completed,
            duration_ms=duration_ms,
        )

    def failed(
        self,
        error: TurnError,
        *,
        completed_at: datetime | None = None,
    ) -> TurnCompletion:
        """Mark the turn failed and return final lifecycle metadata."""
        completed = completed_at or datetime.now(UTC)
        duration_ms = start_to_completed_duration_ms(self.started_at, completed)
        self.turn.status = TurnStatus.FAILED
        self.turn.error = error
        self.turn.completed_at = completed
        self.turn.duration_ms = duration_ms
        return TurnCompletion(
            event=TurnEvent.turn_failed(
                session_id=self.turn.session_id,
                turn_id=self.turn.id,
                error=error,
                reply=self.reply,
            ),
            status=TurnStatus.FAILED,
            error=error,
            completed_at=completed,
            duration_ms=duration_ms,
        )