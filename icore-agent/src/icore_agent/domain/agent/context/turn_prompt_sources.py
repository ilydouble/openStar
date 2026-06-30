"""Loaded prompt source materials for one agent turn."""

from __future__ import annotations

from dataclasses import dataclass, field

from icore_agent.domain.agent.prompt.prompt_envelope import PromptHistoryItem
from icore_agent.domain.agent.session import ContextItem

from .attachments import AgentFileAttachment, AgentImageAttachment


@dataclass(frozen=True, slots=True)
class TurnPromptSources:
    """Prompt inputs loaded before assembling model-visible turn prompts.

    This value is not an agent runtime context object.  It contains only the
    already-loaded materials used to build PromptEnvelope values for one turn.
    IO concerns such as Redis, database reads, file ownership checks, and user
    memory retrieval belong to application services before this value exists.
    """

    summary: str | None
    history_items: list[PromptHistoryItem] = field(default_factory=list)
    image_attachments: list[AgentImageAttachment] = field(default_factory=list)
    file_attachments: list[AgentFileAttachment] = field(default_factory=list)
    user_memory_prompt: str | None = None
    rag_context_items: list[ContextItem] = field(default_factory=list)

    @classmethod
    def empty(cls) -> TurnPromptSources:
        """Return empty prompt sources after source loading fails."""
        return cls(summary=None)

    @property
    def has_attachments(self) -> bool:
        """Return whether any attachment source is present."""
        return bool(self.image_attachments or self.file_attachments)
