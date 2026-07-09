"""Provider-neutral model step results for agent loop execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from icore_agent.contexts.agent.domain.session import AgentMessageItem, ToolCallItem


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


@dataclass(frozen=True, slots=True)
class ModelToolCallStarted:
    """Provider began streaming one tool call."""

    item_id: str
    provider_tool_call_id: str | None = None
    index: int | None = None
    name: str | None = None


@dataclass(frozen=True, slots=True)
class ModelToolCallDelta:
    """One streamed tool-call argument delta from the provider."""

    item_id: str
    arguments_delta: str
    provider_tool_call_id: str | None = None
    index: int | None = None
    name: str | None = None


@dataclass(frozen=True, slots=True)
class ModelToolCallCompleted:
    """Provider finished streaming one tool call."""

    tool_call: ToolCallItem


@dataclass(frozen=True, slots=True)
class ModelStreamWarning:
    """Non-terminal warning emitted while consuming a provider stream."""

    code: str
    message: str
    retryable: bool = False


ModelStreamEvent = (
    ModelTextDelta
    | ModelToolCallStarted
    | ModelToolCallDelta
    | ModelToolCallCompleted
    | ModelStreamWarning
    | ModelStepResult
)
