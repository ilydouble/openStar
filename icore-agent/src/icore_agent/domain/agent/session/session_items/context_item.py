"""Runtime context timeline item."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from icore_agent.domain.agent.roles import ChatCompletionRole

from .base_item import SessionItemBase, SessionItemStatus
from .session_item_type import SessionItemType


class ContextItem(SessionItemBase):
    """Runtime context injected into the model for one turn only.

    Context items are not conversation history and do not mean the user said
    the content.  They carry extra model-visible material such as summaries,
    durable user memory, attachment references, RAG results, permissions, or
    runtime environment notes.
    """

    type: Literal[SessionItemType.CONTEXT] = SessionItemType.CONTEXT
    status: SessionItemStatus = SessionItemStatus.COMPLETED
    kind: str = Field(
        description=(
            "Context source or purpose, such as session_summary, user_memory, "
            "runtime_context, tool_context, attachments, or rag_result."
        ),
    )
    role_hint: Literal[ChatCompletionRole.USER] = Field(
        default=ChatCompletionRole.USER,
        description=(
            "Provider role hint used by prompt adapters.  The current v1 "
            "contract only supports user, so adapters render this item as a "
            "user-role context wrapper message."
        ),
    )
    content: str = Field(
        description=(
            "External context text visible to the model for this turn.  This "
            "text is not persisted as chat history and is not a user utterance."
        ),
    )
