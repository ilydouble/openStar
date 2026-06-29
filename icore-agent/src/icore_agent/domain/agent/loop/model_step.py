"""Provider-neutral model step results for agent loop execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from icore_agent.domain.agent.session import AgentMessageItem, ToolCallItem


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
