"""Async queue bridge for blocking prepared agent runs."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from typing import Any, cast

from icore_agent.domain.agent.prompt import PromptEnvelope
from icore_agent.domain.agent.turn import TurnEvent

from .loop.types import AgentToolEventBridge, PreparedAgentRunner


QueueItem = tuple[str, Any]
AgentInvoker = Callable[[PreparedAgentRunner, PromptEnvelope], Any]


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
    prompt_envelope: PromptEnvelope,
    tool_bridge: AgentToolEventBridge,
    emit_assistant_delta: Callable[[str], None],
    invoke: AgentInvoker | None = None,
) -> threading.Thread:
    """Run a blocking prepared agent invocation in a worker thread."""

    def emit(event: TurnEvent) -> None:
        put_threadsafe(loop=loop, queue=queue, kind="event", payload=event)

    def invoke_runner() -> None:
        try:
            with tool_bridge.bound_to(
                emit=emit,
                emit_assistant_delta=emit_assistant_delta,
            ):
                result = (
                    invoke(runner, prompt_envelope)
                    if invoke is not None
                    else runner(prompt_envelope)
                )
            put_threadsafe(loop=loop, queue=queue,
                           kind="result", payload=result)
        except Exception as exc:
            put_threadsafe(loop=loop, queue=queue, kind="error", payload=exc)
        finally:
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
