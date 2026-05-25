"""Application service for usage, quota decisions, and usage event recording."""

from __future__ import annotations

from typing import Any, Protocol

from icore_agent.domain.user import UserProfile

from .policy import check_quota, consume_quota, ensure_current_usage


class UsageStore(Protocol):
    """Persistence operations needed by usage application workflows."""

    def get_user_by_id(self, user_id: str) -> UserProfile | None:
        """Load one user profile by public id."""
        ...

    def save_user(self, user: UserProfile) -> UserProfile:
        """Persist one changed user profile."""
        ...

    def list_users(self) -> list[UserProfile]:
        """Return all users for admin usage reporting."""
        ...

    def record_usage_event(self, **payload: Any) -> None:
        """Persist one usage event."""
        ...

    def usage_summary(self, user_id: str) -> dict[str, Any]:
        """Return event-based usage summary for one user."""
        ...

    def admin_overview(self, users: list[UserProfile]) -> dict[str, Any]:
        """Return admin overview using the current user set."""
        ...


class UsageService:
    """Coordinate quota policy and token usage updates."""

    def __init__(self, store: UsageStore) -> None:
        """Create a usage service backed by one persistence store."""
        self._store = store

    def record_llm_usage(
        self,
        *,
        user_id: str,
        session_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
    ) -> None:
        """Persist one LLM usage event and update token quota counters."""
        payload = {
            "user_id": user_id,
            "session_id": session_id,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "estimated_cost": round(total_tokens / 1_000_000 * 2.0, 6),
        }
        self._store.record_usage_event(**payload)
        if total_tokens > 0:
            try:
                self.consume_quota(user_id, "tokens", total_tokens)
            except KeyError:
                # Usage event persistence must not fail when a legacy token has no user row.
                return

    def get_usage_summary(self, user_id: str) -> dict[str, Any]:
        """Load event-based usage metrics for one user."""
        return self._store.usage_summary(user_id)

    def get_admin_overview(self) -> dict[str, Any]:
        """Return admin usage metrics using all user profiles."""
        return self._store.admin_overview(self._store.list_users())

    def check_quota(
        self,
        user_id: str,
        resource: str,
        amount: int = 1,
    ) -> tuple[bool, str | None]:
        """Return whether the user can consume more of one quota bucket."""
        user = self._store.get_user_by_id(user_id)
        if user is None:
            return False, "user not found"
        user, usage, should_save = ensure_current_usage(user)
        if should_save:
            user = self._store.save_user(user)
        return check_quota(user, usage, resource, amount)

    def consume_quota(self, user_id: str, resource: str, amount: int = 1) -> None:
        """Consume quota for one accepted operation."""
        user = self._store.get_user_by_id(user_id)
        if user is None:
            raise KeyError(user_id)
        user, usage, should_save = ensure_current_usage(user)
        if should_save:
            user = self._store.save_user(user)
        self._store.save_user(consume_quota(user, usage, resource, amount))
