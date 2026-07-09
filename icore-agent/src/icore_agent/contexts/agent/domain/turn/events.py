"""Domain events emitted while a chat turn runs."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from icore_agent.contexts.agent.domain.session import SessionItem
from icore_agent.shared.identifiers import uuid7
from icore_agent.shared.time.utils import utc_now

from .turn import Turn
from .turn_error import TurnError

_SCHEMA_VERSION = 1


def _new_event_id() -> str:
    """Return a public id for one emitted turn event."""
    return str(uuid7())


class TurnEventKind(StrEnum):
    """Public event kinds for turn streaming."""

    TURN_STARTED = "turn_started"
    ITEM_STARTED = "item_started"
    ITEM_DELTA = "item_delta"
    ITEM_COMPLETED = "item_completed"
    TURN_COMPLETED = "turn_completed"
    TURN_FAILED = "turn_failed"
    TURN_ABORTED = "turn_aborted"
    STREAM_WARNING = "stream_warning"


class TurnEvent(BaseModel):
    """One event in the user-visible turn stream."""

    model_config = ConfigDict(extra="forbid")

    kind: TurnEventKind
    session_id: str
    turn_id: str
    event_id: str = Field(default_factory=_new_event_id)
    seq: int | None = None
    schema_version: int = _SCHEMA_VERSION
    created_at: datetime = Field(default_factory=utc_now)
    run_id: str | None = None
    item_id: str | None = None
    item_type: str | None = None
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
        item_type: str | None = None,
    ) -> TurnEvent:
        """Create an item-delta event."""
        return cls(
            kind=TurnEventKind.ITEM_DELTA,
            session_id=session_id,
            turn_id=turn_id,
            item_id=item_id,
            item_type=item_type,
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
    def stream_warning(
        cls,
        *,
        session_id: str,
        turn_id: str,
        code: str,
        message: str,
        retryable: bool = False,
    ) -> TurnEvent:
        """Create a non-terminal stream warning event."""
        return cls(
            kind=TurnEventKind.STREAM_WARNING,
            session_id=session_id,
            turn_id=turn_id,
            delta={
                "code": code,
                "message": message,
                "retryable": retryable,
            },
        )

    def with_envelope(
        self,
        *,
        seq: int,
        run_id: str | None = None,
    ) -> TurnEvent:
        """Return this event with turn-scoped stream envelope metadata."""
        return self.model_copy(update={
            "seq": seq,
            "run_id": run_id,
            "created_at": self.created_at or utc_now(),
        })

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
            "event_id": self.event_id,
            "seq": self.seq,
            "schema_version": self.schema_version,
            "created_at": _datetime_to_iso(self.created_at),
        }
        if self.run_id is not None:
            payload["run_id"] = self.run_id
        if self.item_id is not None:
            payload["item_id"] = self.item_id
        if self.item_type is not None:
            payload["item_type"] = self.item_type
        if self.item is not None:
            payload["item"] = self.item.model_dump(mode="json")
        if self.delta is not None:
            payload["delta"] = self.delta
        if self.error is not None:
            payload["error"] = self.error.model_dump(mode="json")
        if self.reply is not None:
            payload["reply"] = self.reply
        if self.turn is not None:
            payload["turn"] = _turn_payload(self.turn)
        return payload


def _turn_payload(turn: Turn) -> dict[str, Any]:
    """Project a domain Turn to the public timeline turn shape."""
    return {
        "turn_id": turn.id,
        "session_id": turn.session_id,
        "status": (
            turn.status.value
            if hasattr(turn.status, "value")
            else str(turn.status)
        ),
        "model": turn.model,
        "provider": turn.provider,
        "usage": turn.usage,
        "error": (
            turn.error.model_dump(mode="json")
            if turn.error is not None
            else None
        ),
        "started_at": _datetime_to_iso(turn.started_at),
        "completed_at": _datetime_to_iso(turn.completed_at),
        "duration_ms": turn.duration_ms,
        "items": [
            item.model_dump(mode="json")
            for item in turn.items
        ],
    }


def _datetime_to_iso(value: datetime | None) -> str | None:
    """Return an RFC3339-ish timestamp with a Z suffix for UTC values."""
    if value is None:
        return None
    text = value.isoformat()
    return text.replace("+00:00", "Z")
