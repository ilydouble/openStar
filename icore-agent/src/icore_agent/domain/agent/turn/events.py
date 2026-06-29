"""Domain events emitted while a chat turn runs."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict

from icore_agent.domain.agent.session import SessionItem

from .turn import Turn
from .turn_error import TurnError


class TurnEventKind(StrEnum):
    """Public event kinds for turn streaming."""

    TURN_STARTED = "turn_started"
    ITEM_STARTED = "item_started"
    ITEM_DELTA = "item_delta"
    ITEM_COMPLETED = "item_completed"
    TURN_COMPLETED = "turn_completed"
    TURN_FAILED = "turn_failed"
    TURN_ABORTED = "turn_aborted"


class TurnEvent(BaseModel):
    """One event in the user-visible turn stream."""

    model_config = ConfigDict(extra="forbid")

    kind: TurnEventKind
    session_id: str
    turn_id: str
    item_id: str | None = None
    item: SessionItem | None = None
    delta: dict[str, Any] | None = None
    error: TurnError | None = None
    reply: str | None = None
    turn: Turn | None = None

    @classmethod
    def turn_started(cls, *, session_id: str, turn_id: str) -> TurnEvent:
        """Create a turn-start event."""
        return cls(
            kind=TurnEventKind.TURN_STARTED,
            session_id=session_id,
            turn_id=turn_id,
        )

    @classmethod
    def item_started(
        cls,
        *,
        session_id: str,
        turn_id: str,
        item: SessionItem,
    ) -> TurnEvent:
        """Create an item-start event."""
        return cls(
            kind=TurnEventKind.ITEM_STARTED,
            session_id=session_id,
            turn_id=turn_id,
            item_id=item.id,
            item=item,
        )

    @classmethod
    def item_delta(
        cls,
        *,
        session_id: str,
        turn_id: str,
        item_id: str,
        delta: dict[str, Any],
    ) -> TurnEvent:
        """Create an item-delta event."""
        return cls(
            kind=TurnEventKind.ITEM_DELTA,
            session_id=session_id,
            turn_id=turn_id,
            item_id=item_id,
            delta=delta,
        )

    @classmethod
    def item_completed(
        cls,
        *,
        session_id: str,
        turn_id: str,
        item: SessionItem,
    ) -> TurnEvent:
        """Create an item-completed event."""
        return cls(
            kind=TurnEventKind.ITEM_COMPLETED,
            session_id=session_id,
            turn_id=turn_id,
            item_id=item.id,
            item=item,
        )

    @classmethod
    def turn_completed(
        cls,
        *,
        session_id: str,
        turn_id: str,
        reply: str,
        turn: Turn | None = None,
    ) -> TurnEvent:
        """Create a turn-completed event."""
        return cls(
            kind=TurnEventKind.TURN_COMPLETED,
            session_id=session_id,
            turn_id=turn_id,
            reply=reply,
            turn=turn,
        )

    @classmethod
    def turn_failed(
        cls,
        *,
        session_id: str,
        turn_id: str,
        error: TurnError,
        reply: str | None = None,
        turn: Turn | None = None,
    ) -> TurnEvent:
        """Create a turn-failed event."""
        return cls(
            kind=TurnEventKind.TURN_FAILED,
            session_id=session_id,
            turn_id=turn_id,
            error=error,
            reply=reply,
            turn=turn,
        )

    @classmethod
    def turn_aborted(
        cls,
        *,
        session_id: str,
        turn_id: str,
        reply: str | None = None,
        turn: Turn | None = None,
    ) -> TurnEvent:
        """Create a turn-aborted event."""
        return cls(
            kind=TurnEventKind.TURN_ABORTED,
            session_id=session_id,
            turn_id=turn_id,
            reply=reply,
            turn=turn,
        )

    def to_payload(self) -> dict[str, Any]:
        """Return the JSON payload exposed by the HTTP streaming adapter."""
        payload: dict[str, Any] = {
            "type": self.kind.value if isinstance(self.kind, TurnEventKind) else self.kind,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
        }
        if self.item_id is not None:
            payload["item_id"] = self.item_id
        if self.item is not None:
            payload["item"] = self.item.model_dump(mode="json")
        if self.delta is not None:
            payload["delta"] = self.delta
        if self.error is not None:
            payload["error"] = self.error.model_dump(mode="json")
        if self.reply is not None:
            payload["reply"] = self.reply
        return payload
