"""Domain error model for failed chat turns."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class TurnError(BaseModel):
    """A serializable error captured while executing one turn."""

    model_config = ConfigDict(extra="forbid")

    message: str
    code: str | None = None
    details: dict[str, Any] | None = None
