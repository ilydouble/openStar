"""Aggregate settings assembled from domain-specific settings groups."""

from typing import Any

from .app import AppSettings
from .auth import AuthSettings
from .base import _DOMAINS
from .database import DatabaseSettings
from .llm import LLMSettings
from .logging import LoggingSettings
from .media import MediaSettings
from .memory import MemorySettings
from .rag import RagSettings
from .sequential import SequentialSettings
from .storage import StorageSettings
from .tools import ToolsSettings


class Settings(
    AppSettings,
    LoggingSettings,
    LLMSettings,
    SequentialSettings,
    MemorySettings,
    AuthSettings,
    DatabaseSettings,
    RagSettings,
    ToolsSettings,
    MediaSettings,
    StorageSettings,
):
    """Aggregate runtime settings assembled from all domain-specific groups."""

    env_domains = _DOMAINS

    def __init__(self, **values: Any) -> None:
        """Initialize aggregate settings from explicit values and split env files."""
        super().__init__(**values)

    @property
    def effective_sequential_model(self) -> str:
        """Return the configured sequential model, falling back to the main model."""
        return self.sequential_model or self.effective_model_id()

    def effective_model_id(self) -> str:
        """Resolve the current user's BYOK model override or the default model id."""
        byok = self._runtime_byok()
        if byok.get("enabled"):
            byok_model = self._nonempty(byok.get("model"))
            if byok_model:
                return byok_model
        return self.model_id


# Singleton — import this everywhere; app_settings is an alias for backward compat
settings = Settings()
app_settings = settings
