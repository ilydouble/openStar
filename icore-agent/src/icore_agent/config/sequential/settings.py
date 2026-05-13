from __future__ import annotations

from pydantic import Field

from ..base import DomainSettings


class SequentialSettings(DomainSettings):
    env_domains = ("sequential",)

    sequential_model: str = ""
    sequential_max_steps: int = Field(30, ge=1, le=100)
    sequential_timeout_per_step: int = Field(60, ge=5, le=600)
    sequential_workspace: str = "/tmp/icore-seq-workspace"


sequential_settings = SequentialSettings()
