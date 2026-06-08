"""Minimal Strands Agent loop wrapper."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from icore_agent.domain.chat.session import AgentMessageItem, SessionItemStatus
from icore_agent.domain.chat.turn import TurnEvent
from icore_agent.shared.logging.app_logger import get_logger

from icore_agent.application.agent.async_bridge import (
    AgentInvoker,
    QueueItem,
    patch_runner_callback,
    put_threadsafe,
    start_agent_worker,
)
from icore_agent.application.agent.tool import StrandsToolEventBridge

log = get_logger(__name__)


class AgentRunner(Protocol):
    """Minimal prepared-agent surface used by the loop."""

    messages: list[dict[str, Any]]

    def __call__(self, message: str) -> Any:
        """Run one user message through the prepared agent."""
        ...


@dataclass(frozen=True, slots=True)
class AgentLoopRequest:
    """Inputs needed to run one prepared agent turn."""

    session_id: str
    turn_id: str
    message: str
    runner: AgentRunner
    history_messages: list[dict[str, Any]]
    tool_bridge: StrandsToolEventBridge
    invoke: AgentInvoker | None = None


class AgentLoopError(Exception):
    """Raised when the prepared agent run fails."""


class AgentLoop:
    """Run a prepared Strands Agent and emit item-level turn events."""

    def __init__(self, *, wall_budget_sec: int) -> None:
        """Create a loop with a hard wall-clock budget."""
        self._wall_budget_sec = wall_budget_sec

    async def run(self, request: AgentLoopRequest) -> AsyncIterator[TurnEvent]:
        """Run one prepared agent request and stream domain events."""
        request.runner.messages = request.history_messages
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[QueueItem] = asyncio.Queue()
        assistant_item = AgentMessageItem()
        assistant_text: list[str] = []

        yield TurnEvent.item_started(
            session_id=request.session_id,
            turn_id=request.turn_id,
            item=assistant_item,
        )

        def emit_assistant_delta(token: str) -> None:
            put_threadsafe(
                loop=loop,
                queue=queue,
                kind="assistant_delta",
                payload=token,
            )

        with patch_runner_callback(request.runner, request.tool_bridge.on_callback):
            start_agent_worker(
                loop=loop,
                queue=queue,
                runner=request.runner,
                message=request.message,
                tool_bridge=request.tool_bridge,
                emit_assistant_delta=emit_assistant_delta,
                invoke=request.invoke,
            )
            caught_error = None
            start = loop.time()
            while True:
                if loop.time() - start > self._wall_budget_sec:
                    caught_error = TimeoutError(
                        f"Agent run exceeded {self._wall_budget_sec}s budget"
                    )
                    break
                try:
                    kind, payload = await asyncio.wait_for(
                        queue.get(),
                        timeout=1,
                    )
                except TimeoutError:
                    continue

                if kind == "assistant_delta":
                    text = str(payload)
                    assistant_text.append(text)
                    yield TurnEvent.item_delta(
                        session_id=request.session_id,
                        turn_id=request.turn_id,
                        item_id=assistant_item.id,
                        delta={"text": text},
                    )
                elif kind == "event":
                    yield payload
                elif kind == "result":
                    if not assistant_text:
                        assistant_text.append(str(payload))
                elif kind == "error":
                    caught_error = payload
                elif kind == "done":
                    break

        reply = "".join(assistant_text)
        if caught_error is None:
            yield TurnEvent.item_completed(
                session_id=request.session_id,
                turn_id=request.turn_id,
                item=assistant_item.model_copy(update={
                    "status": SessionItemStatus.COMPLETED,
                    "text": reply,
                    "completed_at": datetime.now(UTC),
                }),
            )
            return

        yield TurnEvent.item_completed(
            session_id=request.session_id,
            turn_id=request.turn_id,
            item=assistant_item.model_copy(update={
                "status": SessionItemStatus.FAILED,
                "text": reply,
                "completed_at": datetime.now(UTC),
            }),
        )
        log.error("agent_loop_failed", error=str(caught_error))
        raise AgentLoopError(str(caught_error)) from caught_error
