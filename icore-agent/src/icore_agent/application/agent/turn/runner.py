"""Agent loop request construction for agent turns."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from icore_agent.application.agent.context import AgentPromptContextManager
from icore_agent.application.agent.loop import AgentLoopRequest
from icore_agent.application.agent.tool import ToolRuntime
from icore_agent.application.agent.tool.catalog import (
    build_orchestrator_tool_definitions,
)
from icore_agent.domain.agent.loop import AgentLoopControl, ModelClient
from icore_agent.domain.agent.turn import Turn
from icore_agent.infrastructure.agent.chat_completions.pi_runner import (
    create_pi_model_client,
)
from icore_agent.shared.logging.app_logger import get_logger

log = get_logger(__name__)

ModelClientFactory = Callable[..., ModelClient]
ModelClientWrapper = Callable[[ModelClient], ModelClient]


class AgentTurnRunnerFactory:
    """Build application loop requests while hiding concrete adapters."""

    def __init__(
        self,
        model_client_factory: ModelClientFactory,
        *,
        file_service: Any | None = None,
        pi_workspace_service: Any | None = None,
    ) -> None:
        """Create a loop-request factory with a model-client factory."""
        self._model_client_factory = model_client_factory
        self._file_service = file_service
        self._pi_workspace_service = pi_workspace_service

    def build_loop_request(
        self,
        *,
        command: Any,
        context: Any,
        turn: Turn,
        model_client_wrapper: ModelClientWrapper | None = None,
        control: AgentLoopControl | None = None,
    ) -> AgentLoopRequest:
        """Build an AgentLoopRequest for one turn."""
        pi_workspace_dir = self._resolve_pi_workspace_dir(command)
        tool_definitions = build_orchestrator_tool_definitions(
            session_id=command.session_id,
            user_id=command.user_id,
            file_service=self._file_service,
        )
        if pi_workspace_dir:
            # Pi mode delegates the whole turn (tool selection and execution)
            # to pi-source-service, so our ToolRuntime stays empty for it.
            model_client = create_pi_model_client(
                session_id=command.session_id,
                workspace_dir=pi_workspace_dir,
                summary=getattr(context, "summary", None),
            )
        else:
            model_client = self._model_client_factory(
                session_id=command.session_id,
                user_id=command.user_id,
            )
        if model_client_wrapper is not None:
            model_client = model_client_wrapper(model_client)
        return AgentLoopRequest(
            session_id=command.session_id,
            turn_id=turn.id,
            turn=turn,
            context_manager=AgentPromptContextManager(
                command=command,
                context=context,
            ),
            model_client=model_client,
            tool_runtime=ToolRuntime(tool_definitions),
            **({"control": control} if control is not None else {}),
        )

    def _resolve_pi_workspace_dir(self, command: Any) -> str | None:
        """Extract the user's selected Pi project into its sandbox directory.

        Returns the absolute path Pi should be confined to, or ``None`` when
        Pi mode isn't using an uploaded project (falls back to pi-service's
        default read-only workspace). Never raises — a missing/foreign/corrupt
        workspace silently degrades to "no project selected" rather than
        failing the whole turn, since the user can simply re-pick a project.
        """
        workspace_id = (getattr(command, "pi_workspace_id", None) or "").strip()
        if not workspace_id or self._pi_workspace_service is None:
            return None
        try:
            from icore_agent.config import settings

            sandbox_root = Path(settings.pi_workspace_sandbox_root) / command.user_id / workspace_id
            resolved = self._pi_workspace_service.extract_into_sandbox(
                owner_user_id=command.user_id,
                workspace_id=workspace_id,
                destination_root=sandbox_root,
            )
            return str(resolved)
        except Exception:
            log.warning(
                "pi_workspace_resolve_failed",
                session_id=command.session_id,
                user_id=command.user_id,
                workspace_id=workspace_id,
                exc_info=True,
            )
            return None
