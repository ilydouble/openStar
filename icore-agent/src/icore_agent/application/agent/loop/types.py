"""Shared application protocols for agent loop execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import AsyncIterator
from typing import Any, Protocol

from icore_agent.domain.agent.prompt import PromptEnvelope
from icore_agent.domain.agent.session import (
    AgentMessageItem,
    SessionItem,
    ToolCallItem,
    UserMessageItem,
)
from icore_agent.domain.agent.tool import ToolDefinition
from icore_agent.domain.agent.turn import Turn


@dataclass(frozen=True, slots=True)
class ModelStepResult:
    """Provider-neutral result from one model sampling step."""

    assistant_item: AgentMessageItem
    tool_calls: list[ToolCallItem] = field(default_factory=list)
    deltas: list[str] = field(default_factory=list)
    usage: dict[str, int] | None = None
    model: str | None = None
    provider: str | None = None
    stop_reason: str = "stop"
    raw_response_id: str | None = None
    raw_payload: Any | None = None


@dataclass(frozen=True, slots=True)
class ModelTextDelta:
    """One streamed assistant text delta from the model provider."""

    text: str


ModelStreamEvent = ModelTextDelta | ModelStepResult


class ModelClient(Protocol):
    """Application-facing model client that samples one PromptEnvelope."""

    async def sample(self, envelope: PromptEnvelope) -> ModelStepResult:
        """Return one model step without executing any requested tools."""
        ...

    async def stream(
        self,
        envelope: PromptEnvelope,
    ) -> AsyncIterator[ModelStreamEvent]:
        """Yield model text deltas and one final sampling result."""
        ...


class PromptContextManager(Protocol):
    """Build model-visible prompts from loaded context and current turn state."""

    def build_prompt(
        self,
        *,
        turn: Turn,
        session_items: list[SessionItem],
        tools: list[ToolDefinition],
    ) -> PromptEnvelope:
        """Build the provider-neutral prompt envelope for one sampling step."""
        ...


class ToolRuntimePort(Protocol):
    """Port for executing tools and exposing model-visible definitions."""

    def visible_tools(self) -> list[ToolDefinition]:
        """Return tool definitions visible to the model."""
        ...

    async def execute(self, tool_calls: list[ToolCallItem]) -> list[ToolCallItem]:
        """Execute requested tool calls and return completed or failed items."""
        ...


class AgentLoopControl(Protocol):
    """Runtime control surface visible to the application agent loop."""

    async def abort_requested(self) -> bool:
        """Return whether the active run should abort cooperatively."""
        ...

    async def drain_steering(self) -> list[UserMessageItem]:
        """Drain runtime steering input for the current turn."""
        ...


class NoopAgentLoopControl:
    """Default loop control used when no runtime shell is installed."""

    async def abort_requested(self) -> bool:
        """Return false because no runtime abort source exists."""
        return False

    async def drain_steering(self) -> list[UserMessageItem]:
        """Return no steering input."""
        return []
