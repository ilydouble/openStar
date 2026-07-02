"""Settings for storage-service backed file assets."""

from __future__ import annotations

from ..base import DomainSettings


class StorageSettings(DomainSettings):
    """Runtime settings for object storage integration."""

    env_domains = ("storage",)

    storage_service_url: str = "http://127.0.0.1:18090"
    storage_service_token: str = "dev-storage-service-token"
    storage_service_timeout: float = 30
    file_storage_bucket: str = "icore-files"
    file_upload_url_expires_in: int = 600

    # Pi Agent uploaded-project workspace archives (durable copies in MinIO).
    pi_workspace_bucket: str = "icore-pi-workspaces"
    # 30 min — 2 GB archives can take a while on slow connections; the
    # presigned PUT URL must stay valid for the whole upload.
    pi_workspace_upload_url_expires_in: int = 1800
    pi_workspace_max_size_mb: int = 2048
    pi_workspace_max_files: int = 100_000
    # Local filesystem root where uploaded project archives are extracted into
    # per-workspace sandbox directories before Pi analyzes them. MUST be a
    # volume shared with pi-source-service, mounted there at PI_WORKSPACE_ROOT
    # (defaults to "<PI_WORKSPACE>/projects" — see pi-source-service/src/server.ts),
    # so the path icore-agent hands to pi-service resolves to the same files on
    # both sides. This is the filesystem-level half of the sandbox boundary —
    # pi-service independently re-validates containment against its own root.
    pi_workspace_sandbox_root: str = "/workspace/projects"


storage_settings = StorageSettings()
