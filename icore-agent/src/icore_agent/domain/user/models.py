"""Domain user models shared across application services."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any


@dataclass(slots=True)
class UserProfile:
    """Persisted account profile without persistence or HTTP concerns."""

    public_id: str
    email: str
    name: str
    plan: str
    plan_label: str
    organization_id: str | None = None
    organization_name: str | None = None
    roles: list[str] = field(default_factory=lambda: ["owner"])
    byok: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] = field(default_factory=dict)
    created_at: int = 0
    updated_at: int = 0

    def with_usage(self, usage: dict[str, Any], *, updated_at: int) -> UserProfile:
        """Return a copy with refreshed usage counters and updated timestamp."""
        return replace(self, usage=dict(usage), updated_at=updated_at)
