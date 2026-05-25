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
        """Persist one LLM cost event and update the internal token counter.

        Tokens are recorded for cost reporting only and do NOT count against
        the user's task quota.  Call consume_task() separately after each
        successfully completed agent turn.
        """
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
                # Track token spend internally; quota enforcement uses tasks.
                self.consume_quota(user_id, "tokens", total_tokens)
            except KeyError:
                # Do not fail cost recording when a legacy row is missing.
                return

    def consume_task(self, user_id: str) -> None:
        """Deduct one task from the user's monthly quota.

        Call this once per successfully completed agent turn, after the reply
        has been persisted.  Errors are swallowed so a missing user row never
        crashes the response path.
        """
        try:
            self.consume_quota(user_id, "tasks", 1)
        except KeyError:
            # Gracefully handle missing user rows (e.g. during local dev).
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
