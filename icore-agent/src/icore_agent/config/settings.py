"""Aggregate settings assembled from domain-specific settings groups."""

from .app import AppSettings
from .auth import AuthSettings
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
    @property
    def effective_sequential_model(self) -> str:
        return self.sequential_model or self.model_id


app_settings = Settings()
settings = app_settings
