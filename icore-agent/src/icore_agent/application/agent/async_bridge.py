"""Async queue bridge for blocking Strands Agent runs."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from typing import Any, cast

from icore_agent.domain.agent.turn import TurnEvent

from .loop.types import PreparedAgentRunner
from .tool import (
    StrandsToolEventBridge,
    reset_parent_callback,
    set_parent_callback,
)


QueueItem = tuple[str, Any]
AgentInvoker = Callable[[PreparedAgentRunner, str], Any]


def put_threadsafe(
    *,
    loop: asyncio.AbstractEventLoop,
    queue: asyncio.Queue[QueueItem],
    kind: str,
    payload: Any,
) -> None:
    """Put one worker event into an asyncio queue from any thread."""
    asyncio.run_coroutine_threadsafe(queue.put((kind, payload)), loop)


def start_agent_worker(
    *,
    loop: asyncio.AbstractEventLoop,
    queue: asyncio.Queue[QueueItem],
    runner: PreparedAgentRunner,
    message: str,
    tool_bridge: StrandsToolEventBridge,
    emit_assistant_delta: Callable[[str], None],
    invoke: AgentInvoker | None = None,
) -> threading.Thread:
    """Run a blocking Strands Agent invocation in a worker thread."""

    def emit(event: TurnEvent) -> None:
        put_threadsafe(loop=loop, queue=queue, kind="event", payload=event)

    def invoke_runner() -> None:
        parent_callback_token = set_parent_callback(tool_bridge.on_callback)
        try:
            with tool_bridge.bound_to(
                emit=emit,
                emit_assistant_delta=emit_assistant_delta,
            ):
                result = (
                    invoke(runner, message)
                    if invoke is not None
                    else runner(message)
                )
            put_threadsafe(loop=loop, queue=queue,
                           kind="result", payload=result)
        except Exception as exc:
            put_threadsafe(loop=loop, queue=queue, kind="error", payload=exc)
        finally:
            reset_parent_callback(parent_callback_token)
            put_threadsafe(loop=loop, queue=queue, kind="done", payload=None)

    thread = threading.Thread(target=invoke_runner, daemon=True)
    thread.start()
    return thread


def patch_runner_callback(
    runner: PreparedAgentRunner,
    callback_handler: Callable[..., None],
) -> AbstractContextManager[None]:
    """Patch test fakes that expose callback_handler after construction."""
    if not hasattr(runner, "callback_handler"):
        return nullcontext()
    runner_with_callback = cast(Any, runner)
    previous = runner_with_callback.callback_handler

    class _Patch:
        def __enter__(self) -> None:
            runner_with_callback.callback_handler = callback_handler

        def __exit__(self, exc_type, exc, traceback) -> None:
            runner_with_callback.callback_handler = previous

    return _Patch()
