"""Serialize user domain models for the HTTP v1 API."""

from __future__ import annotations

from typing import Any

from icore_agent.domain.user import UserProfile


def serialize_user_profile(user: UserProfile) -> dict[str, Any]:
    """Convert a user profile into the stable account API payload."""
    return {
        "id": user.public_id,
        "name": user.name,
        "email": user.email,
        "plan": user.plan,
        "plan_label": user.plan_label,
        "organization_id": user.organization_id or "",
        "organization_name": user.organization_name or "",
        "roles": list(user.roles or ["owner"]),
        "byok": dict(
            user.byok
            or {"enabled": False, "api_key": "", "api_base": "", "model": ""}
        ),
        "usage": dict(user.usage or {}),
        "created_at": int(user.created_at),
        "updated_at": int(user.updated_at),
    }
