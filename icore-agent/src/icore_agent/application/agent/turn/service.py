"""Application service for executing agent turns."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable

from icore_agent.application.agent.context import (
    ConversationMemory,
    dedupe_file_uuids,
    load_agent_context,
)
from icore_agent.application.agent.loop.agent_loop import AgentLoop
from icore_agent.application.agent.loop.types import (
    AgentToolEventBridge,
    PreparedAgentRunner,
)
from icore_agent.application.agent.turn import (
    AgentTurnExecutor,
    AgentTurnRunnerFactory,
    TurnPersistence,
    TurnTranscriptRecorder,
    TurnUsageRecorder,
)
from icore_agent.application.agent.tool import TurnToolProjection
from icore_agent.application.files import FileAssetService
from icore_agent.application.memory import UserMemoryService
from icore_agent.application.usage import UsageService
from icore_agent.domain.agent.turn import Turn, TurnEvent, TurnEventKind
from icore_agent.shared.logging.app_logger import get_logger

from ..commands import AgentTurnCommand
from ..session import AgentSessionService
from .routing import classify_turn_intent

log = get_logger(__name__)

CHAT_STREAM_WALL_BUDGET_SEC = 600

OrchestratorFactory = Callable[..., PreparedAgentRunner]
ToolEventBridgeFactory = Callable[..., AgentToolEventBridge]


class AgentTurnService:
    """Application entrypoint for one user-triggered agent turn."""

    def __init__(
        self,
        *,
        agent_session: AgentSessionService,
        file_service: FileAssetService,
        conversation_memory: ConversationMemory,
        orchestrator_factory: OrchestratorFactory,
        tool_bridge_factory: ToolEventBridgeFactory,
        usage_service: UsageService | None = None,
        user_memory_service: UserMemoryService | None = None,
        wall_budget_sec: int = CHAT_STREAM_WALL_BUDGET_SEC,
        agent_loop: AgentLoop | None = None,
    ) -> None:
        """Create an agent turn service with its application dependencies."""
        self._agent_session = agent_session
        self._file_service = file_service
        self._conversation_memory = conversation_memory
        self._user_memory_service = user_memory_service
        self._usage = TurnUsageRecorder(usage_service)
        self._executor = AgentTurnExecutor(
            agent_loop=agent_loop or AgentLoop(
                wall_budget_sec=wall_budget_sec),
            runner_factory=AgentTurnRunnerFactory(
                orchestrator_factory,
                tool_bridge_factory=tool_bridge_factory,
                file_service=file_service,
            ),
            persistence=TurnPersistence(agent_session),
            transcript=TurnTranscriptRecorder(
                agent_session=agent_session,
                conversation_memory=conversation_memory,
                user_memory_service=user_memory_service,
            ),
            usage=self._usage,
            tool_projection_factory=lambda: TurnToolProjection(agent_session),
        )

    async def run(self, command: AgentTurnCommand) -> Turn:
        """Execute one non-streaming agent turn."""
        self._usage.check_task_quota(command)
        await self._prepare_turn(command)
        context = await self._load_context(command)
        self._usage.record_attachment_quota(command, context)
        async for event in self._executor.run(
            command=command,
            context=context,
        ):
            if event.kind is TurnEventKind.TURN_COMPLETED:
                if event.turn is None:
                    raise RuntimeError(
                        "Agent turn completed without turn state")
                return event.turn
            elif event.kind is TurnEventKind.TURN_FAILED:
                message = event.error.message if event.error is not None else "Agent turn failed"
                raise RuntimeError(message)
        raise RuntimeError("Agent turn ended without completion")

    async def stream(
        self,
        command: AgentTurnCommand,
    ) -> AsyncIterator[TurnEvent]:
        """Prepare one streaming agent turn and return its event stream."""
        self._usage.check_task_quota(command)
        await self._prepare_turn(command)
        context = await self._load_context(command)
        self._usage.record_attachment_quota(command, context)
        return self._executor.run(
            command=command,
            context=context,
        )

    async def _prepare_turn(
        self,
        command: AgentTurnCommand,
    ) -> None:
        """Persist the user-visible request and record turn request metadata."""
        file_uuids = dedupe_file_uuids(command.file_uuids)
        if not command.incognito:
            self._agent_session.ensure_owned_session(
                command.session_id,
                command.user_id,
                title=command.message.strip()[:255],
            )
            metadata = None
            if file_uuids:
                metadata = {"file_uuids": list(file_uuids)}
                caption = (command.display_caption or "").strip()
                if caption:
                    metadata["display_caption"] = caption
            template_id = (command.template_id or "").strip()
            if template_id:
                metadata = metadata or {}
                metadata["template_id"] = template_id
            self._agent_session.save_user_message(
                command.session_id,
                command.user_id,
                command.message,
                metadata=metadata,
            )
        intent = classify_turn_intent(command.agent_message or command.message)
        log.info(
            "agent_turn_request",
            session_id=command.session_id,
            stream=command.stream,
            incognito=command.incognito,
            intent=intent.value,
        )

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
