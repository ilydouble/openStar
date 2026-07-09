"""One-time import of legacy JSON control-plane user profiles into PostgreSQL."""

from __future__ import annotations

from typing import Any

from icore_agent.contexts.account.application.user_import import LegacyUserImportService
from icore_agent.contexts.account.application.workspace import WorkspaceMetadataService

from icore_agent.infrastructure.persistence.sqlalchemy.sync_session import sync_session_scope
from .sqlalchemy_repository import SqlAlchemyUserRepository


def import_legacy_users_from_store(store: Any) -> int:
    """Import user profiles from the JSON store into PostgreSQL when missing."""
    legacy_users = store.list_legacy_json_users()
    if not legacy_users:
        return 0

    workspace = WorkspaceMetadataService()
    imported = 0
    with sync_session_scope() as session:
        service = LegacyUserImportService(SqlAlchemyUserRepository(session))
        for profile in legacy_users:
            user = service.import_profile(profile)
            if user is None:
                continue
            workspace.ensure_organization_for_user(user)
            imported += 1
    return imported
