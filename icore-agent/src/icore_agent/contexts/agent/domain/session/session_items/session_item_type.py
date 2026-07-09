"""Timeline item type values shared by all session item models."""

from enum import StrEnum


class SessionItemType(StrEnum):
    """Supported timeline item kinds in a chat session turn."""

    CONTEXT = "context"
    USER_MESSAGE = "user_message"
    AGENT_MESSAGE = "agent_message"
    REASONING = "reasoning"
    PLAN = "plan"
    TOOL_CALL = "tool_call"
