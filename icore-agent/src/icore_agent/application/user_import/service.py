"""Application service for importing legacy user profile payloads."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from icore_agent.application.usage.policy import (
    current_timestamp,
    default_usage,
    plan_or_trial,
)
from icore_agent.domain.user import UserProfile, UserRepository


class LegacyUserImportService:
    """Convert legacy JSON user payloads into domain profiles."""

    def __init__(self, repository: UserRepository) -> None:
        """Create an import service backed by a user repository."""
        self._repository = repository

    def import_profile(
        self,
        profile: Mapping[str, Any],
    ) -> UserProfile | None:
        """Import one legacy profile, skipping records without id or email."""
        public_id = str(
            profile.get("id") or profile.get("public_id") or ""
        ).strip()
        email = str(profile.get("email") or "").strip().lower()
        if not public_id or not email:
            return None

        plan = plan_or_trial(str(profile.get("plan") or "trial"))
        now = current_timestamp()
        user = UserProfile(
            public_id=public_id,
            email=email,
            name=str(profile.get("name") or email.split("@")[0]).strip(),
            plan=plan.value,
            plan_label=str(profile.get("plan_label") or plan.limits.label),
            organization_id=_optional_string(profile.get("organization_id")),
            organization_name=_optional_string(profile.get("organization_name")),
            roles=_roles(profile.get("roles")),
            byok=_mapping(profile.get("byok"), _default_byok()),
            usage=_mapping(profile.get("usage"), default_usage()),
            created_at=_timestamp(profile.get("created_at"), now),
            updated_at=_timestamp(profile.get("updated_at"), now),
        )
        return self._repository.save(user)


def _optional_string(value: Any) -> str | None:
    """Return a stripped string, or None when empty."""
    text = str(value or "").strip()
    return text or None


def _roles(value: Any) -> list[str]:
    """Return a normalized role list for legacy records."""
    if isinstance(value, list):
        roles = [str(role).strip() for role in value if str(role).strip()]
        return roles or ["owner"]
    return ["owner"]


def _mapping(value: Any, default: dict[str, Any]) -> dict[str, Any]:
    """Return a dict copy when the legacy value is mapping-like."""
    if isinstance(value, Mapping):
        return dict(value)
    return dict(default)


def _default_byok() -> dict[str, Any]:
    """Return the default BYOK settings payload."""
    return {"enabled": False, "api_key": "", "api_base": "", "model": ""}


def _timestamp(value: Any, default: int) -> int:
    """Return a numeric timestamp from a legacy value."""
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default
