"""Provider-neutral tool definitions for application-owned agent tools."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

JSONSchema = dict[str, Any]
PreparedArguments = dict[str, Any]
ToolExecutionResult = Any
ToolExecutor = Callable[
    [str, PreparedArguments, "ToolExecutionContext"],
    ToolExecutionResult | Awaitable[ToolExecutionResult],
]
PrepareArguments = Callable[[Any], PreparedArguments]


@dataclass(frozen=True, slots=True)
class ToolExecutionContext:
    """Runtime context passed to a structured tool executor."""

    tool_call_id: str
    invocation_state: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Provider-neutral definition for one application agent tool."""

    name: str
    label: str
    description: str
    parameters: JSONSchema
    execute: ToolExecutor
    prompt_snippet: str | None = None
    prepare_arguments: PrepareArguments | None = None

    def __post_init__(self) -> None:
        """Validate required tool definition fields early."""
        if not self.name.strip():
            raise ValueError("tool name is required")
        if not self.description.strip():
            raise ValueError(f"tool {self.name!r} description is required")
        if not isinstance(self.parameters, dict):
            raise TypeError("tool parameters must be a JSON schema dict")
