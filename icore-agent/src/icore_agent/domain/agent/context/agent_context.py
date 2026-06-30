"""Pure agent context assembly rules for one turn."""

from __future__ import annotations

from dataclasses import dataclass

from icore_agent.domain.agent.prompt import PromptEnvelope, PromptHistoryItem
from icore_agent.domain.agent.session import (
    ContextItem,
    UserInput,
    UserInputType,
    UserMessageItem,
)
from icore_agent.domain.agent.tool import ToolChoice, ToolDefinition

from .attachments import AgentFileAttachment, AgentImageAttachment


@dataclass(frozen=True, slots=True)
class AgentContext:
    """Loaded runtime materials used to assemble an agent prompt envelope.

    The context is model-visible for the current turn but is not conversation
    history.  IO concerns such as Redis, database reads, and file ownership
    checks belong to application services before this value is constructed.
    """

    summary: str | None
    history_items: list[PromptHistoryItem]
    has_rag: bool
    image_attachments: list[AgentImageAttachment]
    file_attachments: list[AgentFileAttachment]
    user_memory_prompt: str | None = None

    @classmethod
    def empty(cls) -> AgentContext:
        """Return an empty context after context loading fails."""
        return cls(
            summary=None,
            history_items=[],
            has_rag=False,
            image_attachments=[],
            file_attachments=[],
            user_memory_prompt=None,
        )

    @property
    def has_attachments(self) -> bool:
        """Return whether file, image, or RAG context is present."""
        return bool(
            self.has_rag
            or self.image_attachments
            or self.file_attachments
        )

    def to_context_items(
        self,
        *,
        include_image_refs: bool = True,
    ) -> list[ContextItem]:
        """Build model-visible runtime context items for PromptEnvelope."""
        items: list[ContextItem] = []
        if self.summary:
            items.append(ContextItem(
                kind="session_summary",
                content=f"Earlier conversation summary:\n{self.summary}",
            ))
        if self.user_memory_prompt:
            items.append(ContextItem(
                kind="user_memory",
                content=self.user_memory_prompt,
            ))
        if include_image_refs:
            items.extend(
                attachment.to_context_item()
                for attachment in self.image_attachments
            )
        items.extend(
            attachment.to_context_item()
            for attachment in self.file_attachments
        )
        return items

    def to_current_user_inputs(
        self,
        user_text: str,
        *,
        include_image_inputs: bool,
    ) -> list[UserInput]:
        """Build the current user item content for this turn."""
        inputs = [
            UserInput(
                type=UserInputType.TEXT,
                text=user_text,
            )
        ]
        if include_image_inputs:
            for attachment in self.image_attachments:
                inputs.extend(attachment.to_user_inputs())
        return inputs


def build_prompt_envelope(
    *,
    base_instructions: str,
    context: AgentContext,
    user_text: str,
    tools: list[ToolDefinition],
    tool_choice: ToolChoice = ToolChoice.AUTO,
    include_image_inputs: bool = False,
) -> PromptEnvelope:
    """Build a provider-neutral prompt envelope from loaded context materials."""
    return PromptEnvelope(
        base_instructions=base_instructions,
        context_items=context.to_context_items(
            include_image_refs=not include_image_inputs,
        ),
        history_items=context.history_items,
        current_user_item=UserMessageItem(
            content=context.to_current_user_inputs(
                user_text,
                include_image_inputs=include_image_inputs,
            ),
        ),
        tools=tools,
        tool_choice=tool_choice,
    )
