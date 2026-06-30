"""Agent loop request construction for agent turns."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from icore_agent.application.agent.context import AgentTurnPromptBuilder
from icore_agent.application.agent.loop import AgentLoopRequest
from icore_agent.application.agent.tool import ToolRuntime
from icore_agent.application.agent.tool.catalog import (
    build_orchestrator_tool_definitions,
)
from icore_agent.domain.agent.loop import AgentLoopControl, ModelClient
from icore_agent.domain.agent.turn import Turn

ModelClientFactory = Callable[..., ModelClient]
ModelClientWrapper = Callable[[ModelClient], ModelClient]


class AgentTurnRunnerFactory:
    """Build application loop requests while hiding concrete adapters."""

    def __init__(
        self,
        model_client_factory: ModelClientFactory,
        *,
        file_service: Any | None = None,
    ) -> None:
        """Create a loop-request factory with a model-client factory."""
        self._model_client_factory = model_client_factory
        self._file_service = file_service

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
        tool_definitions = build_orchestrator_tool_definitions(
            session_id=command.session_id,
            user_id=command.user_id,
            file_service=self._file_service,
        )
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
            context_manager=AgentTurnPromptBuilder(
                command=command,
                sources=context,
            ),
            model_client=model_client,
            tool_runtime=ToolRuntime(tool_definitions),
            **({"control": control} if control is not None else {}),
        )
