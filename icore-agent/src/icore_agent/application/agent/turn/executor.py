"""Agent turn lifecycle executor."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable

from icore_agent.application.agent.loop.agent_loop import AgentLoop, AgentLoopError
from icore_agent.domain.agent.turn import TurnError, TurnEvent

from .lifecycle import TurnLifecycle
from .persistence import TurnPersistence
from .runner import AgentTurnRunnerFactory
from .transcript import TurnTranscriptRecorder
from .usage import TurnUsageRecorder
from ..tool import TurnToolProjection


class AgentTurnExecutor:
    """Coordinate one agent turn between started and final lifecycle events."""

    def __init__(
        self,
        *,
        agent_loop: AgentLoop,
        runner_factory: AgentTurnRunnerFactory,
        persistence: TurnPersistence,
        transcript: TurnTranscriptRecorder,
        usage: TurnUsageRecorder,
        tool_projection_factory: Callable[[], TurnToolProjection],
    ) -> None:
        """Create the executor with its turn-scoped collaborators."""
        self._agent_loop = agent_loop
        self._runner_factory = runner_factory
        self._persistence = persistence
        self._transcript = transcript
        self._usage = usage
        self._tool_projection_factory = tool_projection_factory

    async def run(
        self,
        *,
        command,
        context,
    ) -> AsyncIterator[TurnEvent]:
        """Run a prepared command through one agent turn lifecycle."""
        lifecycle = TurnLifecycle.start(session_id=command.session_id)
        self._persistence.create(command, lifecycle.turn)
        yield lifecycle.started_event()

        user_event = lifecycle.user_message_event(command.message)
        self._persistence.persist_event(command, user_event)
        yield user_event

        projection = self._tool_projection_factory()
        request = self._runner_factory.build_loop_request(
            command=command,
            context=context,
            turn_id=lifecycle.turn.id,
            invoke=self._usage.invoke_with_usage(command),
        )
        try:
            async for event in self._agent_loop.run(request):
                lifecycle.apply_agent_event(event)
                self._persistence.persist_event(command, event)
                projection.persist_event(command, event)
                yield event
        except AgentLoopError as exc:
            error = TurnError(message=str(exc), code=type(exc).__name__)
            final = lifecycle.failed(error)
            self._persistence.complete(
                command,
                turn_id=lifecycle.turn.id,
                status=final.status,
                error=final.error,
                completed_at=final.completed_at,
                duration_ms=final.duration_ms,
            )
            yield final.event
            return

        session_compressed = await self._transcript.append_memory_pair(
            command,
            lifecycle.reply,
        )
        assistant_message_id = self._transcript.save_assistant_message(
            command,
            lifecycle.reply,
        )
        projection.attach_to_assistant(
            command,
            assistant_message_id=assistant_message_id,
        )
        self._usage.consume_task(command)
        await self._transcript.maybe_extract_user_memory(
            command,
            session_compressed,
        )
        final = lifecycle.completed()
        self._persistence.complete(
            command,
            turn_id=lifecycle.turn.id,
            status=final.status,
            error=final.error,
            completed_at=final.completed_at,
            duration_ms=final.duration_ms,
        )
        yield final.event
