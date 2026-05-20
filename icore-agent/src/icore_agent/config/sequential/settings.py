from __future__ import annotations

from typing import Any

from pydantic import Field

from ..base import DomainSettings


class SequentialSettings(DomainSettings):
    """Sequential-agent settings loaded from the sequential dotenv domain."""

    env_domains = ("sequential",)

    sequential_model: str = ""
    sequential_max_steps: int = Field(30, ge=1, le=100)
    sequential_timeout_per_step: int = Field(60, ge=5, le=600)
    sequential_workspace: str = "/tmp/icore-seq-workspace"

    def __init__(self, **values: Any) -> None:
        """Initialize sequential-agent settings from explicit values and domain env files."""
        super().__init__(**values)


sequential_settings = SequentialSettings()
