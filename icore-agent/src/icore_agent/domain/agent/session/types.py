"""Session item discriminated union."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from .agent_message_item import AgentMessageItem
from .context_item import ContextItem
from .plan_item import PlanItem
from .reasoning_item import ReasoningItem
from .tool_call_item import ToolCallItem
from .user_message_item import UserMessageItem

SessionItem = Annotated[
    ContextItem
    | UserMessageItem
    | AgentMessageItem
    | ReasoningItem
    | PlanItem
    | ToolCallItem,
    Field(discriminator="type"),
]
