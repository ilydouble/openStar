"""Shared base class for domain-scoped environment-backed settings."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict

_DOMAINS = (
    "app",
    "database",
    "logging",
    "llm",
    "sequential",
    "memory",
    "auth",
    "rag",
    "tools",
    "media",
)


def dotenv_dir() -> Path:
    configured = os.getenv("ICORE_AGENT_DOTENV_DIR")
    if configured:
        return Path(configured)
    cwd_dotenv = Path.cwd() / "dotenv"
    if cwd_dotenv.is_dir():
        return cwd_dotenv
    return Path(__file__).resolve().parents[3] / "dotenv"


def domain_env_files(*domains: str) -> tuple[str, ...]:
    base = dotenv_dir()
    return tuple(str(base / f".env.{domain}") for domain in domains)


def all_domain_env_files() -> tuple[str, ...]:
    return domain_env_files(*_DOMAINS)


class DomainSettings(BaseSettings):
    env_domains: ClassVar[tuple[str, ...]] = ()

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def __init__(self, **values: Any) -> None:
        if "_env_file" not in values and self.env_domains:
            values["_env_file"] = domain_env_files(*self.env_domains)
        super().__init__(**values)
