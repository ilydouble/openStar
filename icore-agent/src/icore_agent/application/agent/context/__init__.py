"""Agent context assembly package."""

from .agent_context import AgentContext
from .attachments import dedupe_file_uuids
from .loader import load_agent_context
from icore_agent.domain.agent.context import (
    AgentFileAttachment,
    AgentImageAttachment,
)
from .ports import (
    AgentSessionReader,
    ConversationMemory,
    FileContextReader,
    UserMemoryPromptBuilder,
)

__all__ = [
    "AgentContext",
    "AgentFileAttachment",
    "AgentImageAttachment",
    "AgentSessionReader",
    "ConversationMemory",
    "FileContextReader",
    "UserMemoryPromptBuilder",
    "dedupe_file_uuids",
    "load_agent_context",
]
