"""Chat completion protocol role values."""

from enum import Enum


class ChatCompletionRole(str, Enum):
    """Role values accepted by chat completion compatible model APIs."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
