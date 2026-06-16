"""Strands Agent assembly for agent turns."""

from __future__ import annotations

from typing import Any

from strands import Agent
from strands.agent.conversation_manager.sliding_window_conversation_manager import (
    SlidingWindowConversationManager,
)
from strands.tools.executors import SequentialToolExecutor

from icore_agent.application.agent.sys_prompt import (
    BuildSystemPromptOptions,
    build_system_prompt,
)
from icore_agent.application.agent.tool.catalog import (
    build_orchestrator_tool_definitions,
)
from icore_agent.config import settings
from icore_agent.shared.logging.app_logger import get_logger

from .model_factory import create_litellm_model
from .tool_adapter import make_agent_tool

log = get_logger(__name__)

PreparedStrandsAgent = Any


def create_strands_orchestrator(
    callback_handler=None,
    summary: str | None = None,
    session_id: str = "",
    hooks: list[Any] | None = None,
    user_id: str = "",
    user_memory_prompt: str | None = None,
    file_service: Any | None = None,
) -> PreparedStrandsAgent:
    """Create a fresh Strands Agent via LiteLLM for one agent turn."""
    _ = summary, user_memory_prompt
    selected_model = settings.effective_model_id()
    model = create_litellm_model(
        model_id=selected_model,
        max_tokens=settings.agent_max_tokens,
        temperature=settings.agent_temperature,
        user_id=user_id,
        session_id=session_id,
    )

    conversation_manager = SlidingWindowConversationManager(window_size=40)
    tool_definitions = build_orchestrator_tool_definitions(
        session_id=session_id,
        user_id=user_id,
        file_service=file_service,
    )
    system_prompt = str(build_system_prompt(BuildSystemPromptOptions(
        tools=tool_definitions,
    )))
    tools = [make_agent_tool(definition) for definition in tool_definitions]

    orchestrator = Agent(
        model=model,
        system_prompt=system_prompt,
        callback_handler=callback_handler,
        conversation_manager=conversation_manager,
        tools=tools,
        hooks=hooks or [],
        # Execute tools serially to avoid provider RPM spikes when a single
        # response emits multiple tool calls.
        tool_executor=SequentialToolExecutor(),
    )

    log.info(
        "orchestrator_created",
        model=selected_model,
        n_tools=len(tools),
    )
    return orchestrator
