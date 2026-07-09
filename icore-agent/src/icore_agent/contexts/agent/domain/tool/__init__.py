"""Domain tool contracts shared by agent prompt and runtime adapters."""

from .tool_definition import (
    JSONSchema,
    PrepareArguments,
    PreparedArguments,
    ToolDefinition,
    ToolExecutionContext,
    ToolExecutionResult,
    ToolExecutor,
)
from .tool_selection_modes import ToolChoice

__all__ = [
    "JSONSchema",
    "PrepareArguments",
    "PreparedArguments",
    "ToolChoice",
    "ToolDefinition",
    "ToolExecutionContext",
    "ToolExecutionResult",
    "ToolExecutor",
]
