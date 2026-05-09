"""Shared base class for environment-backed settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class DomainSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
