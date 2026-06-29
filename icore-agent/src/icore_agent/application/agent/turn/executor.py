"""Agent turn lifecycle executor."""

from __future__ import annotations

from collections.abc import AsyncIterator

from icore_agent.application.agent.loop.agent_loop import AgentLoop, AgentLoopError
from icore_agent.domain.agent.turn import TurnError, TurnEvent

from .lifecycle import TurnLifecycle
from .persistence import TurnPersistence
from .runner import AgentTurnRunnerFactory
from .transcript import TurnTranscriptRecorder
from .usage import TurnUsageRecorder


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
    ) -> None:
        """Create the executor with its turn-scoped collaborators."""
        self._agent_loop = agent_loop
        self._runner_factory = runner_factory
        self._persistence = persistence
        self._transcript = transcript
        self._usage = usage

    async def run(
        self,
        *,
        command,
        context,
        lifecycle: TurnLifecycle,
        user_event: TurnEvent,
    ) -> AsyncIterator[TurnEvent]:
        """Run a prepared command through one agent turn lifecycle."""
        yield lifecycle.started_event()
        yield user_event

        request = self._runner_factory.build_loop_request(
            command=command,
            context=context,
            turn_id=lifecycle.turn.id,
            invoke=self._usage.invoke_with_usage(command),
        )
        for context_item in request.prompt_envelope.context_items:
            context_event = TurnEvent.item_completed(
                session_id=command.session_id,
                turn_id=lifecycle.turn.id,
                item=context_item,
            )
            lifecycle.apply_agent_event(context_event)
            self._persistence.persist_event(command, context_event)
        try:
            async for event in self._agent_loop.run(request):
                lifecycle.apply_agent_event(event)
                self._persistence.persist_event(command, event)
                yield event
        except AgentLoopError as exc:
            error = TurnError(message=str(exc), code=type(exc).__name__)
            usage_metadata = self._usage.turn_usage()
            _apply_turn_usage(lifecycle, usage_metadata)
            final = lifecycle.failed(error)
            self._persistence.complete(
                command,
                turn_id=lifecycle.turn.id,
                status=final.status,
                error=final.error,
                completed_at=final.completed_at,
                duration_ms=final.duration_ms,
                **usage_metadata,
            )
            yield final.event
            return

        session_compressed = await self._transcript.append_memory_pair(
            command,
            lifecycle.reply,
        )
        self._usage.consume_task(command)
        await self._transcript.maybe_extract_user_memory(
            command,
            session_compressed,
        )
        usage_metadata = self._usage.turn_usage()
        _apply_turn_usage(lifecycle, usage_metadata)
        final = lifecycle.completed()
        self._persistence.complete(
            command,
            turn_id=lifecycle.turn.id,
            status=final.status,
            error=final.error,
            completed_at=final.completed_at,
            duration_ms=final.duration_ms,
            **usage_metadata,
        )
        yield final.event


def _apply_turn_usage(
    lifecycle: TurnLifecycle,
    usage_metadata: dict,
) -> None:
    """Copy captured usage metadata onto the in-memory domain turn."""
    lifecycle.turn.model = usage_metadata.get("model")
    lifecycle.turn.provider = usage_metadata.get("provider")
    lifecycle.turn.usage = usage_metadata.get("usage")
