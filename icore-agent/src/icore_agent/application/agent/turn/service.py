"""Application service for executing agent turns."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

from icore_agent.application.agent.context import (
    ConversationMemory,
    dedupe_file_uuids,
    load_agent_context,
)
from icore_agent.application.agent.loop.agent_loop import AgentLoop
from icore_agent.application.agent.loop import ModelClient
from icore_agent.application.agent.runtime import (
    AgentRunControl,
    AgentRunControlResult,
    AgentRuntime,
    InMemoryAgentRunStore,
)
from icore_agent.application.agent.turn import (
    AgentTurnExecutor,
    AgentTurnRunnerFactory,
    TurnLifecycle,
    TurnPersistence,
    TurnTranscriptRecorder,
    TurnUsageRecorder,
)
from icore_agent.application.files import FileAssetService
from icore_agent.application.memory import UserMemoryService
from icore_agent.application.usage import UsageService
from icore_agent.domain.agent.session import UserMessageItem
from icore_agent.domain.agent.turn import Turn, TurnEvent, TurnEventKind
from icore_agent.shared.logging.app_logger import get_logger

from ..commands import AgentTurnCommand
from ..session import AgentSessionService
from .routing import classify_turn_intent

log = get_logger(__name__)

CHAT_STREAM_WALL_BUDGET_SEC = 600

ModelClientFactory = Callable[..., ModelClient]


class AgentTurnService:
    """Application entrypoint for one user-triggered agent turn."""

    def __init__(
        self,
        *,
        agent_session: AgentSessionService,
        file_service: FileAssetService,
        conversation_memory: ConversationMemory,
        model_client_factory: ModelClientFactory,
        usage_service: UsageService | None = None,
        user_memory_service: UserMemoryService | None = None,
        wall_budget_sec: int = CHAT_STREAM_WALL_BUDGET_SEC,
        agent_loop: AgentLoop | None = None,
        agent_runtime: AgentRuntime | None = None,
    ) -> None:
        """Create an agent turn service with its application dependencies."""
        self._agent_session = agent_session
        self._file_service = file_service
        self._conversation_memory = conversation_memory
        self._user_memory_service = user_memory_service
        self._runtime = agent_runtime or AgentRuntime(
            run_store=InMemoryAgentRunStore(),
        )
        self._usage = TurnUsageRecorder(usage_service)
        self._executor = AgentTurnExecutor(
            agent_loop=agent_loop or AgentLoop(
                wall_budget_sec=wall_budget_sec),
            runner_factory=AgentTurnRunnerFactory(
                model_client_factory,
                file_service=file_service,
            ),
            persistence=TurnPersistence(agent_session),
            transcript=TurnTranscriptRecorder(
                agent_session=agent_session,
                conversation_memory=conversation_memory,
                user_memory_service=user_memory_service,
            ),
            usage=self._usage,
        )

    async def run(self, command: AgentTurnCommand) -> Turn:
        """Execute one non-streaming agent turn."""
        self._usage.check_task_quota(command)
        events = await self._runtime.stream(
            command,
            lambda control: self._run_events(command, control),
        )
        async for event in events:
            if event.kind is TurnEventKind.TURN_COMPLETED:
                if event.turn is None:
                    raise RuntimeError(
                        "Agent turn completed without turn state")
                return event.turn
            elif event.kind is TurnEventKind.TURN_FAILED:
                message = event.error.message if event.error is not None else "Agent turn failed"
                raise RuntimeError(message)
            elif event.kind is TurnEventKind.TURN_ABORTED:
                raise RuntimeError("Agent turn aborted")
        raise RuntimeError("Agent turn ended without completion")

    async def stream(
        self,
        command: AgentTurnCommand,
    ) -> AsyncIterator[TurnEvent]:
        """Prepare one streaming agent turn and return its event stream."""
        self._usage.check_task_quota(command)
        return await self._runtime.stream(
            command,
            lambda control: self._run_events(command, control),
        )

    async def abort(
        self,
        *,
        session_id: str,
        user_id: str,
    ) -> AgentRunControlResult:
        """Request cooperative abort for the active session run."""
        self._agent_session.assert_owned_session(session_id, user_id)
        return await self._runtime.abort(
            session_id=session_id,
            user_id=user_id,
        )

    async def steer(
        self,
        *,
        session_id: str,
        user_id: str,
        message: str,
    ) -> AgentRunControlResult:
        """Queue steering input for the active session run."""
        self._agent_session.assert_owned_session(session_id, user_id)
        return await self._runtime.steer(
            session_id=session_id,
            user_id=user_id,
            message=message,
        )

    async def follow_up(
        self,
        *,
        session_id: str,
        user_id: str,
        message: str,
    ) -> AgentRunControlResult:
        """Queue follow-up input for a later turn boundary."""
        self._agent_session.assert_owned_session(session_id, user_id)
        return await self._runtime.follow_up(
            session_id=session_id,
            user_id=user_id,
            message=message,
        )

    async def _run_events(
        self,
        command: AgentTurnCommand,
        control: AgentRunControl,
    ) -> AsyncIterator[TurnEvent]:
        """Prepare context and run the executor for one locked runtime run."""
        lifecycle, user_event = await self._prepare_turn(command)
        context = await self._load_context(command)
        self._usage.record_attachment_quota(command, context)
        async for event in self._executor.run(
            command=command,
            context=context,
            lifecycle=lifecycle,
            user_event=user_event,
            control=control,
        ):
            yield event

    async def _prepare_turn(
        self,
        command: AgentTurnCommand,
    ) -> tuple[TurnLifecycle, TurnEvent]:
        """Create the turn boundary and persist its initial user item."""
        file_uuids = dedupe_file_uuids(command.file_uuids)
        usage_metadata = self._usage.turn_usage()
        lifecycle = TurnLifecycle.start(
            session_id=command.session_id,
            model=usage_metadata["model"],
            provider=usage_metadata["provider"],
        )
        metadata = _build_user_item_metadata(
            file_uuids=file_uuids,
            display_caption=command.display_caption,
            template_id=command.template_id,
        )
        user_event = lifecycle.user_message_event(
            command.message,
            metadata=metadata,
        )
        if not command.incognito:
            self._agent_session.ensure_owned_session(
                command.session_id,
                command.user_id,
                title=command.message.strip()[:255],
            )
            self._agent_session.start_turn(
                command.session_id,
                command.user_id,
                turn=lifecycle.turn,
                user_item=_require_user_item(user_event),
                title=command.message.strip()[:255],
            )
        intent = classify_turn_intent(command.agent_message or command.message)
        log.info(
            "agent_turn_request",
            session_id=command.session_id,
            stream=command.stream,
            incognito=command.incognito,
            intent=intent.value,
        )
        return lifecycle, user_event

    async def _load_context(self, command: AgentTurnCommand):
        """Load prompt context for one prepared command."""
        return await load_agent_context(
            session_id=command.session_id,
            file_uuids=command.file_uuids,
            user_id=command.user_id,
            user_message=command.message,
            incognito=command.incognito,
            file_service=self._file_service,
            agent_session=self._agent_session,
            conversation_memory=self._conversation_memory,
            user_memory_service=self._user_memory_service,
        )


def _build_user_item_metadata(
    *,
    file_uuids: tuple[str, ...],
    display_caption: str | None,
    template_id: str | None,
) -> dict[str, Any]:
    """Build persisted metadata for the current turn's UserMessageItem."""
    metadata: dict[str, Any] = {}
    if file_uuids:
        metadata["file_uuids"] = list(file_uuids)
        caption = (display_caption or "").strip()
        if caption:
            metadata["display_caption"] = caption
    template = (template_id or "").strip()
    if template:
        metadata["template_id"] = template
    return metadata


def _require_user_item(event: TurnEvent) -> UserMessageItem:
    """Return the user item from a prepared user-message event."""
    if isinstance(event.item, UserMessageItem):
        return event.item
    raise RuntimeError("prepared turn did not create a user message item")
