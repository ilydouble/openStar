"""Safe persistence adapter for agent turn lifecycle state."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from icore_agent.domain.agent.session import SessionItem
from icore_agent.domain.agent.turn import Turn, TurnError, TurnEvent, TurnStatus
from icore_agent.shared.logging.app_logger import get_logger

log = get_logger(__name__)


class TurnPersistence:
    """Persist turn and session-item state without owning execution flow."""

    def __init__(self, agent_session: Any) -> None:
        """Create a persistence adapter over durable agent session storage."""
        self._agent_session = agent_session

    def create(self, command: Any, turn: Turn) -> None:
        """Persist a turn start without failing an otherwise runnable request."""
        if command.incognito:
            return
        try:
            self._agent_session.create_turn(
                command.session_id,
                command.user_id,
                turn,
            )
        except (AttributeError, PermissionError, LookupError) as exc:
            log.warning(
                "turn_persist_start_failed",
                session_id=command.session_id,
                error=str(exc),
            )

    def persist_event(self, command: Any, event: TurnEvent) -> None:
        """Append a turn event and persist the carried session item if any."""
        self.append_event(command, event)
        if event.item is None:
            return
        self.upsert_item(command, event.turn_id, event.item)

    def append_event(self, command: Any, event: TurnEvent) -> None:
        """Persist an append-only event record without failing the turn."""
        if command.incognito:
            return
        try:
            self._agent_session.append_turn_event(
                command.session_id,
                command.user_id,
                turn_id=event.turn_id,
                event=event,
            )
        except (AttributeError, PermissionError, LookupError) as exc:
            log.warning(
                "turn_event_append_failed",
                session_id=command.session_id,
                turn_id=event.turn_id,
                event_id=event.event_id,
                error=str(exc),
            )

    def upsert_item(self, command: Any, turn_id: str, item: SessionItem) -> None:
        """Persist a turn item without failing an already running request."""
        if command.incognito:
            return
        try:
            self._agent_session.upsert_session_item(
                command.session_id,
                command.user_id,
                turn_id=turn_id,
                item=item,
            )
        except (AttributeError, PermissionError, LookupError) as exc:
            log.warning(
                "turn_item_persist_failed",
                session_id=command.session_id,
                turn_id=turn_id,
                item_id=getattr(item, "id", ""),
                error=str(exc),
            )

    def complete(
        self,
        command: Any,
        *,
        turn_id: str,
        status: TurnStatus,
        error: TurnError | None,
        completed_at: datetime,
        duration_ms: int | None,
        model: str | None = None,
        provider: str | None = None,
        usage: dict[str, Any] | None = None,
    ) -> None:
        """Persist final turn state without failing response delivery."""
        if command.incognito:
            return
        try:
            self._agent_session.complete_turn(
                command.session_id,
                command.user_id,
                turn_id=turn_id,
                status=status,
                error=error,
                completed_at=completed_at,
                duration_ms=duration_ms,
                model=model,
                provider=provider,
                usage=usage,
            )
        except (AttributeError, PermissionError, LookupError) as exc:
            log.warning(
                "turn_persist_complete_failed",
                session_id=command.session_id,
                turn_id=turn_id,
                error=str(exc),
            )
