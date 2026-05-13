"""Aggregate settings assembled from domain-specific settings groups."""

from .app import AppSettings
from .auth import AuthSettings
from .base import _DOMAINS
from .database import DatabaseSettings
from .llm import LLMSettings
from .media import MediaSettings
from .memory import MemorySettings
from .rag import RagSettings
from .sequential import SequentialSettings
from .tools import ToolsSettings


class Settings(
    AppSettings,
    LLMSettings,
    SequentialSettings,
    MemorySettings,
    AuthSettings,
    DatabaseSettings,
    RagSettings,
    ToolsSettings,
    MediaSettings,
):
    env_domains = _DOMAINS

    @property
    def effective_sequential_model(self) -> str:
        return self.sequential_model or self.effective_model_id()

    def effective_model_id(self) -> str:
        try:
            from ..control_plane.context import current_runtime_user

            user = current_runtime_user()
        except Exception:
            user = None
        byok = (user or {}).get("byok") or {}
        return byok.get("model") or self.model_id



# Singleton — import this everywhere; app_settings is an alias for backward compat
settings = Settings()
app_settings = settings
