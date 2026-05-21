"""Settings for storage-service backed file assets."""

from __future__ import annotations

from ..base import DomainSettings


class StorageSettings(DomainSettings):
    """Runtime settings for object storage integration."""

    env_domains = ("storage",)

    storage_service_url: str = "http://storage-service:8090"
    storage_service_token: str = "dev-storage-service-token"
    storage_service_timeout: float = 30
    file_storage_bucket: str = "icore-files"
    file_upload_url_expires_in: int = 600


storage_settings = StorageSettings()
