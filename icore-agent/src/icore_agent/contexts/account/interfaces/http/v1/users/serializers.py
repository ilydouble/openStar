"""Serialize user domain models for the HTTP v1 API."""

from __future__ import annotations

from typing import Any

from icore_agent.contexts.account.domain.user import AuthenticatedUser, UserProfile


def mask_api_key(api_key: str | None) -> str:
    """Return a redacted API key showing only the last four characters."""
    key = (api_key or "").strip()
    if not key:
        return ""
    if len(key) <= 4:
        return "****"
    suffix = key[-4:]
    if key.startswith("sk-"):
        return f"sk-****{suffix}"
    return f"****{suffix}"


def serialize_byok(byok: dict[str, Any] | None) -> dict[str, Any]:
    """Convert stored BYOK settings into the public account API payload."""
    payload = dict(
        byok or {"enabled": False, "api_key": "", "api_base": "", "model": ""},
    )
    payload["api_key"] = mask_api_key(str(payload.get("api_key") or ""))
    return payload


def serialize_user_profile(user: UserProfile | AuthenticatedUser) -> dict[str, Any]:
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
        "byok": serialize_byok(dict(user.byok or {})),
        "usage": dict(user.usage or {}),
        "created_at": int(user.created_at),
        "updated_at": int(user.updated_at),
    }
