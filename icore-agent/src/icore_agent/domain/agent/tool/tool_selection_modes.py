"""Provider-neutral tool selection modes for agent model requests."""

from enum import StrEnum


class ToolChoice(StrEnum):
    """Provider-neutral tool selection modes."""

    AUTO = "auto"
    NONE = "none"
    REQUIRED = "required"
