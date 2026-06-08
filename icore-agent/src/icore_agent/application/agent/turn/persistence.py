"""Safe persistence adapter for agent turn lifecycle state."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from icore_agent.domain.chat.session import SessionItem
from icore_agent.domain.chat.turn import Turn, TurnError, TurnEvent, TurnStatus
from icore_agent.shared.logging.app_logger import get_logger

log = get_logger(__name__)


class TurnPersistence:
    """Persist turn and session-item state without owning execution flow."""

    def __init__(self, chat_history: Any) -> None:
        """Create a persistence adapter over durable chat history."""
        self._chat_history = chat_history

    def create(self, command: Any, turn: Turn) -> None:
        """Persist a turn start without failing an otherwise runnable request."""
        if command.incognito:
            return
        try:
            self._chat_history.create_turn(
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
        """Persist the session item carried by an item event."""
        if event.item is None:
            return
        self.upsert_item(command, event.turn_id, event.item)

    def upsert_item(self, command: Any, turn_id: str, item: SessionItem) -> None:
        """Persist a turn item without failing an already running request."""
        if command.incognito:
            return
        try:
            self._chat_history.upsert_session_item(
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
    ) -> None:
        """Persist final turn state without failing response delivery."""
        if command.incognito:
            return
        try:
            self._chat_history.complete_turn(
                command.session_id,
                command.user_id,
                turn_id=turn_id,
                status=status,
                error=error,
                completed_at=completed_at,
                duration_ms=duration_ms,
            )
        except (AttributeError, PermissionError, LookupError) as exc:
            log.warning(
                "turn_persist_complete_failed",
                session_id=command.session_id,
                turn_id=turn_id,
                error=str(exc),
            )
