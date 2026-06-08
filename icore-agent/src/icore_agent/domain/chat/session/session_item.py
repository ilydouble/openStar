"""Domain models for user-visible items inside one chat session turn."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from icore_agent.domain.identifiers import uuid7


def _new_id() -> str:
    """Return a stable public domain id."""
    return str(uuid7())


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class SessionItemType(StrEnum):
    """Supported timeline item kinds in a chat session turn."""

    USER_MESSAGE = "user_message"
    AGENT_MESSAGE = "agent_message"
    REASONING = "reasoning"
    PLAN = "plan"
    TOOL_CALL = "tool_call"


class SessionItemStatus(StrEnum):
    """Lifecycle status shared by user-visible session items."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class SessionItemBase(BaseModel):
    """Base model for one item in a chat turn timeline."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    id: str = Field(default_factory=_new_id)
    status: SessionItemStatus = SessionItemStatus.IN_PROGRESS
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None


class UserInputType(StrEnum):
    """Supported user input blocks."""

    TEXT = "text"
    IMAGE = "image"


class UserInput(BaseModel):
    """One typed block in a user message item."""

    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    type: UserInputType
    text: str | None = None
    image_file_uuid: str | None = None


class UserMessageItem(SessionItemBase):
    """A user message submitted at the start of a turn."""

    type: Literal["user_message"] = "user_message"
    status: SessionItemStatus = SessionItemStatus.COMPLETED
    content: list[UserInput]


class AgentMessageItem(SessionItemBase):
    """An assistant response item, optionally built by streaming deltas."""

    type: Literal["agent_message"] = "agent_message"
    text: str = ""


class ReasoningItem(SessionItemBase):
    """A model reasoning summary item."""

    type: Literal["reasoning"] = "reasoning"
    text: str = ""


class PlanItem(SessionItemBase):
    """An agent plan item shown in the turn timeline."""

    type: Literal["plan"] = "plan"
    text: str = ""


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
    """A tool invocation requested by the model and executed by Strands."""

    type: Literal["tool_call"] = "tool_call"
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


SessionItem = Annotated[
    UserMessageItem | AgentMessageItem | ReasoningItem | PlanItem | ToolCallItem,
    Field(discriminator="type"),
]
