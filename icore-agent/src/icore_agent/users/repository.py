from __future__ import annotations

import time
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..control_plane.constants import Plan, Usage
from .mappers import user_to_api_dict
from .models import User


def _default_usage() -> dict[str, int]:
    """Return a mutable copy of the default usage counters."""
    return asdict(Usage())


def _plan_or_free(value: str) -> Plan:
    """Resolve a persisted plan string, defaulting unknown legacy values to free."""
    try:
        return Plan(value)
    except ValueError:
        return Plan.FREE


class UserRepository:
    """Repository for account user persistence in PostgreSQL."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_user_name(self, user_name: str) -> User | None:
        """Load a user by legacy user_name (email alias)."""
        result = self._session.execute(
            select(User).where(User.user_name == user_name)
        )
        return result.scalar_one_or_none()

    def get_by_public_id(self, public_id: str) -> User | None:
        """Load a user by external public id."""
        result = self._session.execute(
            select(User).where(User.public_id == public_id)
        )
        return result.scalar_one_or_none()

    def get_by_email(self, email: str) -> User | None:
        """Load a user by email address."""
        normalized = email.strip().lower()
        result = self._session.execute(
            select(User).where(User.email == normalized)
        )
        return result.scalar_one_or_none()

    def list_all(self) -> list[User]:
        """Return every persisted account profile."""
        result = self._session.execute(
            select(User).order_by(User.created_at.asc()))
        return list(result.scalars().all())

    def upsert_from_legacy_dict(self, payload: dict[str, Any]) -> User | None:
        """Insert or update one user row from a legacy JSON control-plane profile."""
        public_id = str(payload.get("id") or "").strip()
        email = str(payload.get("email") or "").strip().lower()
        if not public_id or not email:
            return None

        existing = self.get_by_public_id(public_id) or self.get_by_email(email)
        now = int(time.time())
        plan = _plan_or_free(str(payload.get("plan") or Plan.FREE.value))
        plan_label = str(payload.get("plan_label") or plan.limits.label)
        usage = dict(payload.get("usage") or _default_usage())
        byok = dict(
            payload.get("byok")
            or {"enabled": False, "api_key": "", "api_base": "", "model": ""}
        )
        roles = list(payload.get("roles") or ["owner"])

        if existing is not None:
            existing.name = str(payload.get("name") or existing.name)
            existing.plan = plan.value
            existing.plan_label = plan_label
            existing.organization_id = str(
                payload.get(
                    "organization_id") or existing.organization_id or ""
            ) or None
            existing.organization_name = str(
                payload.get(
                    "organization_name") or existing.organization_name or ""
            ) or None
            existing.roles = roles
            existing.byok = byok
            existing.usage = usage
            existing.updated_at = int(payload.get("updated_at") or now)
            self._session.flush()
            return existing

        user = User(
            public_id=public_id,
            user_name=email,
            password_hash="",
            email=email,
            name=str(payload.get("name") or email),
            plan=plan.value,
            plan_label=plan_label,
            organization_id=str(payload.get("organization_id") or "") or None,
            organization_name=str(payload.get(
                "organization_name") or "") or None,
            roles=roles,
            byok=byok,
            usage=usage,
            created_at=int(payload.get("created_at") or now),
            updated_at=int(payload.get("updated_at") or now),
        )
        self._session.add(user)
        self._session.flush()
        return user

    def create_trial_user(
        self,
        *,
        name: str,
        email: str,
        organization_id: str,
        organization_name: str,
    ) -> User:
        """Create a new trial/free account profile."""
        now = int(time.time())
        normalized_email = email.strip().lower()
        display_name = name.strip() or "Trial User"
        user = User(
            public_id=str(uuid.uuid4()),
            user_name=normalized_email,
            password_hash="",
            email=normalized_email,
            name=display_name,
            plan=Plan.FREE.value,
            plan_label=Plan.FREE.limits.label,
            organization_id=organization_id,
            organization_name=organization_name,
            roles=["owner"],
            byok={"enabled": False, "api_key": "",
                  "api_base": "", "model": ""},
            usage=_default_usage(),
            created_at=now,
            updated_at=now,
        )
        self._session.add(user)
        self._session.flush()
        return user

    def update_organization_name(self, user: User, organization_name: str) -> User:
        """Persist a renamed organization label on the user profile."""
        user.organization_name = organization_name.strip()
        user.updated_at = int(time.time())
        self._session.flush()
        return user

    def update_byok(
        self,
        user: User,
        *,
        api_key: str,
        api_base: str,
        model: str,
    ) -> dict[str, Any]:
        """Persist BYOK credentials for one user."""
        user.byok = {
            "enabled": bool(api_key),
            "api_key": api_key.strip(),
            "api_base": api_base.strip(),
            "model": model.strip(),
        }
        user.updated_at = int(time.time())
        self._session.flush()
        return dict(user.byok)

    def update_plan(
        self,
        user: User,
        *,
        new_plan: str,
        byok_enabled: bool = False,
        byok_api_key: str = "",
        byok_api_base: str = "",
        byok_model: str = "",
    ) -> User:
        """Update the billing plan and optional BYOK settings."""
        plan = Plan(new_plan)
        user.plan = plan.value
        user.plan_label = plan.limits.label
        if byok_enabled:
            user.byok = {
                "enabled": True,
                "api_key": byok_api_key.strip(),
                "api_base": byok_api_base.strip(),
                "model": byok_model.strip(),
            }
        user.updated_at = int(time.time())
        self._session.flush()
        return user

    def ensure_usage(self, user: User) -> dict[str, Any]:
        """Return usage counters, resetting the monthly quota period when needed."""
        usage = dict(user.usage or _default_usage())
        if self._should_reset_quota(int(usage.get("quota_period_start", 0) or 0)):
            usage = _default_usage()
            usage["quota_period_start"] = self._quota_period_start()
            user.usage = usage
            user.updated_at = int(time.time())
            self._session.flush()
        elif not user.usage:
            user.usage = usage
            self._session.flush()
        return dict(user.usage or _default_usage())

    def check_quota(self, user: User, kind: str, amount: int = 1) -> tuple[bool, str | None]:
        """Return whether the user can consume more of the given quota bucket."""
        usage = self.ensure_usage(user)
        limits = _plan_or_free(user.plan).limits
        if kind == "messages":
            limit = limits.message_limit
            used = int(usage["message_count"])
        elif kind == "tokens":
            limit = limits.token_limit
            used = int(usage["token_count"])
        elif kind == "images":
            limit = limits.image_limit
            used = int(usage["image_count"])
        else:
            limit = limits.attachment_limit
            used = int(usage["attachment_count"])
        if limit and used + amount > limit:
            return False, f"{kind} quota exceeded for {user.plan}"
        return True, None

    def consume_quota(self, user: User, kind: str, amount: int = 1) -> None:
        """Increment one quota bucket for the user."""
        usage = self.ensure_usage(user)
        if kind == "messages":
            usage["message_count"] = int(usage["message_count"]) + amount
        elif kind == "tokens":
            usage["token_count"] = int(usage["token_count"]) + amount
        elif kind == "images":
            usage["image_count"] = int(usage["image_count"]) + amount
        else:
            usage["attachment_count"] = int(usage["attachment_count"]) + amount
        user.usage = usage
        user.updated_at = int(time.time())
        self._session.flush()

    def add_token_usage(self, user: User, total_tokens: int) -> None:
        """Increment token usage counters after an LLM call."""
        usage = self.ensure_usage(user)
        usage["token_count"] = int(usage["token_count"]) + total_tokens
        user.usage = usage
        user.updated_at = int(time.time())
        self._session.flush()

    def to_api_dict(self, user: User) -> dict[str, Any]:
        """Return the API payload for one user row."""
        return user_to_api_dict(user)

    @staticmethod
    def _should_reset_quota(quota_period_start: int) -> bool:
        """Return whether monthly quota counters should reset."""
        if quota_period_start == 0:
            return True
        period_start = datetime.fromtimestamp(quota_period_start, tz=UTC)
        now = datetime.now(UTC)
        if now.year > period_start.year:
            return True
        return now.year == period_start.year and now.month > period_start.month

    @staticmethod
    def _quota_period_start() -> int:
        """Return the Unix timestamp for the current quota period start."""
        now = datetime.now(UTC)
        period_start = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=UTC)
        return int(period_start.timestamp())
