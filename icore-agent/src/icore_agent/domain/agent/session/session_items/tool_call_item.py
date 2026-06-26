"""Tool call timeline item."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from .base_item import SessionItemBase
from .session_item_type import SessionItemType


class ToolCallStatus(StrEnum):
    """Lifecycle state for an LLM-requested tool call."""

    STREAMING = "streaming"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DECLINED = "declined"


class ToolCallType(StrEnum):
    """Supported tool-call families."""

    FUNCTION = "function"
    MCP = "mcp"


class ToolFunction(BaseModel):
    """Function-call name and arguments."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    arguments_text: str = ""
    arguments_json: dict[str, Any] | None = None


class ToolCallResult(BaseModel):
    """Normalized tool-call result for the timeline."""

    model_config = ConfigDict(extra="forbid")

    content: str | None = None
    structured_content: dict[str, Any] | None = None


class ToolCallError(BaseModel):
    """Normalized tool-call error for the timeline."""

    model_config = ConfigDict(extra="forbid")

    message: str
    code: str | None = None


class ToolCallItem(SessionItemBase):
    """A tool invocation requested by the model and executed by the runtime."""

    type: Literal[SessionItemType.TOOL_CALL] = SessionItemType.TOOL_CALL
    status: ToolCallStatus = ToolCallStatus.RUNNING
    provider: str | None = None
    provider_tool_call_id: str | None = None
    index: int | None = None
    tool_type: ToolCallType = ToolCallType.FUNCTION
    function: ToolFunction
    result: ToolCallResult | None = None
    error: ToolCallError | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
