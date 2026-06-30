"""Agent context assembly package."""

from .attachments import dedupe_file_uuids
from .loader import load_agent_context
from .manager import AgentPromptContextManager
from icore_agent.domain.agent.context import (
    AgentContext,
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
    "AgentPromptContextManager",
    "AgentSessionReader",
    "ConversationMemory",
    "FileContextReader",
    "UserMemoryPromptBuilder",
    "dedupe_file_uuids",
    "load_agent_context",
]
