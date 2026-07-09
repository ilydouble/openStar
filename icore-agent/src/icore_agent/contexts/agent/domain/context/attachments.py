"""Attachment references loaded for an agent turn."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from icore_agent.contexts.agent.domain.session import (
    ContextItem,
    UserInput,
    UserInputType,
)


def _json_value(value: Any) -> str:
    """Render an attachment metadata value as a quoted JSON string."""
    return json.dumps(str(value or ""), ensure_ascii=False)


@dataclass(frozen=True, slots=True)
class AgentImageAttachment:
    """Image attachment reference passed from file assets into agent context."""

    filename: str
    ref: str
    file_uuid: str

    def to_context_item(self) -> ContextItem:
        """Return metadata-only context visible to the model for this image."""
        return ContextItem(
            kind="image_attachment",
            content=(
                "image_attachment "
                f"filename={_json_value(self.filename)} "
                f"uuid={_json_value(self.file_uuid)} "
                f"ref={_json_value(self.ref)}"
            ),
        )

    def to_user_inputs(self) -> list[UserInput]:
        """Return multimodal current-user input blocks for this image."""
        return [
            UserInput(
                type=UserInputType.TEXT,
                text=(
                    "Attached image available to the model: "
                    f"filename={_json_value(self.filename)} "
                    f"uuid={_json_value(self.file_uuid)}"
                ),
            ),
            UserInput(
                type=UserInputType.IMAGE,
                image_file_uuid=self.file_uuid,
                image_url=self.ref,
            ),
        ]


@dataclass(frozen=True, slots=True)
class AgentFileAttachment:
    """Non-image file attachment reference passed into agent context."""

    filename: str
    file_uuid: str

    def to_context_item(self) -> ContextItem:
        """Return metadata-only context visible to the model for this file."""
        return ContextItem(
            kind="file_attachment",
            content=(
                "file_attachment "
                f"filename={_json_value(self.filename)} "
                f"uuid={_json_value(self.file_uuid)}\n"
                "Use read_uploaded_file with the uuid when file_attachment "
                "contents are needed."
            ),
        )
