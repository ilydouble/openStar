"""Prepared-runner construction for agent turns."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from icore_agent.application.agent.loop.agent_loop import AgentLoopRequest, AgentRunner
from icore_agent.application.agent.tool import StrandsToolEventBridge

OrchestratorFactory = Callable[..., AgentRunner]


class AgentTurnRunnerFactory:
    """Build provider-specific runners while exposing an agent-turn request."""

    def __init__(self, orchestrator_factory: OrchestratorFactory) -> None:
        """Create a runner factory from the existing orchestrator factory."""
        self._orchestrator_factory = orchestrator_factory

    def build_loop_request(
        self,
        *,
        command: Any,
        route: Any,
        context: Any,
        turn_id: str,
        invoke: Callable[[AgentRunner, str], Any] | None,
    ) -> AgentLoopRequest:
        """Build an AgentLoopRequest for one turn."""
        tool_bridge = StrandsToolEventBridge(
            session_id=command.session_id,
            turn_id=turn_id,
        )
        runner = self.build_runner(
            command=command,
            route=route,
            context=context,
            tool_bridge=tool_bridge,
        )
        return AgentLoopRequest(
            session_id=command.session_id,
            turn_id=turn_id,
            message=command.agent_message or command.message,
            runner=runner,
            history_messages=context.strands_history,
            tool_bridge=tool_bridge,
            invoke=invoke,
        )

    def build_runner(
        self,
        *,
        command: Any,
        route: Any,
        context: Any,
        tool_bridge: StrandsToolEventBridge,
    ) -> AgentRunner:
        """Create one prepared Strands runner for AgentLoop."""
        orchestrator = self._orchestrator_factory(
            callback_handler=tool_bridge.on_callback,
            summary=context.summary,
            attachments_text=context.attachments_text,
            image_attachments=context.image_attachment_payloads,
            data_attachments=context.data_attachment_payloads,
            session_id=command.session_id,
            hooks=[tool_bridge],
            user_id=command.user_id,
            user_memory_prompt=context.user_memory_prompt,
        )
        return cast(AgentRunner, orchestrator)
