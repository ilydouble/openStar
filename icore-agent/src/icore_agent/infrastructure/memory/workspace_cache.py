"""Redis cache for workspace team and project list payloads."""

from __future__ import annotations

import json
from typing import Any

import redis

from icore_agent.config import settings
from icore_agent.shared.logging.app_logger import get_logger

log = get_logger(__name__)


class WorkspaceCache:
    """Sync Redis cache for frequently accessed workspace metadata."""

    def __init__(self) -> None:
        self._client: redis.Redis | None = None

    def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    def _team_key(self, user_id: str) -> str:
        return f"icore:workspace:team:{user_id}"

    def _projects_key(self, user_id: str) -> str:
        return f"icore:workspace:projects:{user_id}"

    def get_team_profile(self, user_id: str) -> dict[str, Any] | None:
        """Return a cached team profile payload when present."""
        raw = self._get_client().get(self._team_key(user_id))
        if not raw:
            return None
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            log.warning("workspace_cache_decode_error", kind="team", user_id=user_id)
            return None

    def set_team_profile(self, user_id: str, payload: dict[str, Any]) -> None:
        """Cache one team profile payload."""
        self._get_client().set(
            self._team_key(user_id),
            json.dumps(payload, ensure_ascii=False),
            ex=settings.memory_ttl_seconds,
        )

    def get_project_list(self, user_id: str) -> dict[str, Any] | None:
        """Return a cached project list payload when present."""
        raw = self._get_client().get(self._projects_key(user_id))
        if not raw:
            return None
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            log.warning("workspace_cache_decode_error", kind="projects", user_id=user_id)
            return None

    def set_project_list(self, user_id: str, payload: dict[str, Any]) -> None:
        """Cache one project list payload."""
        self._get_client().set(
            self._projects_key(user_id),
            json.dumps(payload, ensure_ascii=False),
            ex=settings.memory_ttl_seconds,
        )

    def invalidate_user(self, user_id: str) -> None:
        """Drop cached workspace payloads for one user."""
        client = self._get_client()
        client.delete(self._team_key(user_id), self._projects_key(user_id))


workspace_cache = WorkspaceCache()
