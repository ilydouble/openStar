"""Application service for executing chat turns."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable

from icore_agent.application.agent import AgentLoop, AgentRunner
from icore_agent.application.agent.context import (
    ConversationMemory,
    dedupe_file_uuids,
    load_agent_context,
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
from icore_agent.domain.chat.turn import TurnEventKind
from icore_agent.shared.logging.app_logger import get_logger

from ..commands import ChatTurnCommand
from ..events import ChatStreamEvent, ChatTurnResult
from ..routing import ChatRoutingDecision, resolve_routing
from .history_service import ChatHistoryService

log = get_logger(__name__)

CHAT_STREAM_WALL_BUDGET_SEC = 600

OrchestratorFactory = Callable[..., AgentRunner]


class ChatTurnService:
    """Legacy chat entrypoint that delegates agent turn execution."""

    def __init__(
        self,
        *,
        chat_history: ChatHistoryService,
        file_service: FileAssetService,
        conversation_memory: ConversationMemory,
        orchestrator_factory: OrchestratorFactory,
        usage_service: UsageService | None = None,
        user_memory_service: UserMemoryService | None = None,
        wall_budget_sec: int = CHAT_STREAM_WALL_BUDGET_SEC,
        agent_loop: AgentLoop | None = None,
    ) -> None:
        """Create a chat turn service with its application dependencies."""
        self._chat_history = chat_history
        self._file_service = file_service
        self._conversation_memory = conversation_memory
        self._user_memory_service = user_memory_service
        self._usage = TurnUsageRecorder(usage_service)
        self._executor = AgentTurnExecutor(
            agent_loop=agent_loop or AgentLoop(
                wall_budget_sec=wall_budget_sec),
            runner_factory=AgentTurnRunnerFactory(orchestrator_factory),
            persistence=TurnPersistence(chat_history),
            transcript=TurnTranscriptRecorder(
                chat_history=chat_history,
                conversation_memory=conversation_memory,
                user_memory_service=user_memory_service,
            ),
            usage=self._usage,
            tool_projection_factory=lambda: TurnToolProjection(chat_history),
        )

    async def run(self, command: ChatTurnCommand) -> ChatTurnResult:
        """Execute one non-streaming chat turn."""
        self._usage.check_task_quota(command)
        route = await self._prepare_turn(command)
        context = await self._load_context(command)
        self._usage.record_attachment_quota(command, context)
        reply = ""
        turn_id = None
        async for event in self._executor.run(
            command=command,
            route=route,
            context=context,
        ):
            turn_id = event.turn_id
            if event.kind is TurnEventKind.TURN_COMPLETED:
                reply = event.reply or ""
            elif event.kind is TurnEventKind.TURN_FAILED:
                message = event.error.message if event.error is not None else "Agent turn failed"
                raise RuntimeError(message)
        return ChatTurnResult(
            session_id=command.session_id,
            reply=reply,
            turn_id=turn_id,
        )

    async def stream(
        self,
        command: ChatTurnCommand,
    ) -> AsyncIterator[ChatStreamEvent]:
        """Prepare one streaming chat turn and return its application event stream."""
        self._usage.check_task_quota(command)
        route = await self._prepare_turn(command)
        context = await self._load_context(command)
        self._usage.record_attachment_quota(command, context)
        return self._executor.run(
            command=command,
            route=route,
            context=context,
        )

    async def _prepare_turn(
        self,
        command: ChatTurnCommand,
    ) -> ChatRoutingDecision:
        """Persist the user turn and return its routing decision."""
        file_uuids = dedupe_file_uuids(command.file_uuids)
        if not command.incognito:
            self._chat_history.ensure_owned_session(
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
            self._chat_history.save_user_message(
                command.session_id,
                command.user_id,
                command.message,
                metadata=metadata,
            )
        route = resolve_routing(command.agent_message or command.message)
        log.info(
            "chat_request",
            session_id=command.session_id,
            stream=command.stream,
            incognito=command.incognito,
            intent=route.intent.value,
        )
        return route

    async def _load_context(self, command: ChatTurnCommand):
        """Load prompt context for one prepared command."""
        return await load_agent_context(
            session_id=command.session_id,
            file_uuids=command.file_uuids,
            user_id=command.user_id,
            user_message=command.message,
            incognito=command.incognito,
            file_service=self._file_service,
            chat_history=self._chat_history,
            conversation_memory=self._conversation_memory,
            user_memory_service=self._user_memory_service,
        )
