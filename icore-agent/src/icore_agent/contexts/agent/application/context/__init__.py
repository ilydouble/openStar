"""Agent context assembly package."""

from .attachments import dedupe_file_uuids
from .builder import AgentTurnPromptBuilder
from .loader import load_turn_prompt_sources
from icore_agent.contexts.agent.domain.context import (
    AgentFileAttachment,
    AgentImageAttachment,
    TurnPromptSources,
)
from .ports import (
    AgentSessionReader,
    ConversationMemory,
    FileContextReader,
    UserMemoryPromptBuilder,
)

__all__ = [
    "AgentFileAttachment",
    "AgentImageAttachment",
    "AgentTurnPromptBuilder",
    "AgentSessionReader",
    "ConversationMemory",
    "FileContextReader",
    "TurnPromptSources",
    "UserMemoryPromptBuilder",
    "dedupe_file_uuids",
    "load_turn_prompt_sources",
]
