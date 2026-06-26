"""Prepared-runner construction for agent turns."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from icore_agent.application.agent.loop.agent_loop import AgentLoopRequest
from icore_agent.application.agent.loop.types import (
    AgentToolEventBridge,
    PreparedAgentRunner,
)
from icore_agent.application.agent.prompt import build_agent_prompt_envelope
from icore_agent.application.agent.tool import ToolDefinition
from icore_agent.application.agent.tool.catalog import (
    build_orchestrator_tool_definitions,
)
from icore_agent.domain.agent.prompt import PromptEnvelope

OrchestratorFactory = Callable[..., PreparedAgentRunner]
ToolEventBridgeFactory = Callable[..., AgentToolEventBridge]


class AgentTurnRunnerFactory:
    """Build provider-specific runners while exposing an agent-turn request."""

    def __init__(
        self,
        orchestrator_factory: OrchestratorFactory,
        *,
        tool_bridge_factory: ToolEventBridgeFactory,
        file_service: Any | None = None,
    ) -> None:
        """Create a runner factory from the existing orchestrator factory."""
        self._orchestrator_factory = orchestrator_factory
        self._tool_bridge_factory = tool_bridge_factory
        self._file_service = file_service

    def build_loop_request(
        self,
        *,
        command: Any,
        context: Any,
        turn_id: str,
        invoke: Callable[[PreparedAgentRunner, PromptEnvelope], Any] | None,
    ) -> AgentLoopRequest:
        """Build an AgentLoopRequest for one turn."""
        tool_bridge = self._tool_bridge_factory(
            session_id=command.session_id,
            turn_id=turn_id,
        )
        tool_definitions = build_orchestrator_tool_definitions(
            session_id=command.session_id,
            user_id=command.user_id,
            file_service=self._file_service,
        )
        prompt_envelope = build_agent_prompt_envelope(
            command=command,
            context=context,
            tool_definitions=tool_definitions,
        )
        runner = self.build_runner(
            command=command,
            prompt_envelope=prompt_envelope,
            tool_definitions=tool_definitions,
            tool_bridge=tool_bridge,
        )
        return AgentLoopRequest(
            session_id=command.session_id,
            turn_id=turn_id,
            prompt_envelope=prompt_envelope,
            runner=runner,
            tool_bridge=tool_bridge,
            invoke=invoke,
        )

    def build_runner(
        self,
        *,
        command: Any,
        prompt_envelope: PromptEnvelope,
        tool_definitions: list[ToolDefinition],
        tool_bridge: AgentToolEventBridge,
    ) -> PreparedAgentRunner:
        """Create one prepared runner for AgentLoop."""
        orchestrator = self._orchestrator_factory(
            callback_handler=tool_bridge.on_callback,
            session_id=command.session_id,
            hooks=[tool_bridge],
            user_id=command.user_id,
            prompt_envelope=prompt_envelope,
            tool_definitions=tool_definitions,
        )
        return cast(PreparedAgentRunner, orchestrator)
