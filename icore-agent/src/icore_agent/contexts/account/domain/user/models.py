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


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """Authenticated domain user context for request-scoped application work."""

    public_id: str
    email: str
    name: str
    roles: tuple[str, ...] = ("owner",)
    organization_id: str | None = None
    organization_name: str | None = None
    plan: str = ""
    plan_label: str = ""
    byok: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] = field(default_factory=dict)
    created_at: int = 0
    updated_at: int = 0

    @classmethod
    def from_profile(cls, profile: UserProfile) -> AuthenticatedUser:
        """Create an authenticated request context from a persisted user profile."""
        return cls(
            public_id=profile.public_id,
            email=profile.email,
            name=profile.name,
            roles=tuple(profile.roles or ["owner"]),
            organization_id=profile.organization_id,
            organization_name=profile.organization_name,
            plan=profile.plan,
            plan_label=profile.plan_label,
            byok=dict(profile.byok or {}),
            usage=dict(profile.usage or {}),
            created_at=int(profile.created_at),
            updated_at=int(profile.updated_at),
        )
