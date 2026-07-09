"""BYOK credential helpers for account updates."""

from __future__ import annotations


def resolve_api_key_for_update(incoming: str | None, existing: str | None) -> str:
    """Keep the stored key when the client omits it or sends a masked placeholder."""
    value = (incoming or "").strip()
    if not value or "****" in value:
        return (existing or "").strip()
    return value
