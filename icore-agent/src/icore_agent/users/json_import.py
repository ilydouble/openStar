"""One-time import of legacy JSON control-plane user profiles into PostgreSQL."""

from __future__ import annotations

from typing import Any

from ..database.sync_session import sync_session_scope
from .repository import UserRepository


def import_legacy_users_from_store(store: Any) -> int:
    """Import user profiles from the JSON store into PostgreSQL when missing."""
    legacy_users = store.list_legacy_json_users()
    if not legacy_users:
        return 0

    imported = 0
    with sync_session_scope() as session:
        repo = UserRepository(session)
        for profile in legacy_users:
            user = repo.upsert_from_legacy_dict(profile)
            if user is None:
                continue
            store.ensure_organization_for_user(repo.to_api_dict(user))
            imported += 1
    return imported
