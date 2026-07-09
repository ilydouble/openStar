"""Repository contract for durable user memory persistence."""

from __future__ import annotations

from typing import Protocol

from .models import UserMemoryFact, UserMemoryProfile


class UserMemoryRepository(Protocol):
    """Persistence operations for user memory profiles and facts."""

    def get_or_create_profile(self, user_id: str) -> UserMemoryProfile:
        """Load one user memory profile, creating an empty row when missing."""
        ...

    def save_profile(self, profile: UserMemoryProfile) -> UserMemoryProfile:
        """Persist profile counters and stable preference keys."""
        ...

    def list_active_facts(self, user_id: str) -> list[UserMemoryFact]:
        """Return active facts for one user ordered by recency."""
        ...

    def find_active_fact(
        self,
        user_id: str,
        category: str,
        key: str,
    ) -> UserMemoryFact | None:
        """Return one active fact by category and key when present."""
        ...

    def list_active_facts_for_slot(
        self,
        user_id: str,
        category: str,
        key: str,
    ) -> list[UserMemoryFact]:
        """Return active facts for one category/key slot."""
        ...

    def save_fact(self, fact: UserMemoryFact) -> UserMemoryFact:
        """Insert or update one memory fact row."""
        ...

    def count_active_facts(self, user_id: str) -> int:
        """Return how many active facts a user currently has."""
        ...

    def mark_facts_accessed(self, fact_ids: list[int], *, accessed_at: int) -> None:
        """Increment access counters for facts injected into a turn."""
        ...

    def get_active_fact_by_id(
        self,
        user_id: str,
        fact_id: int,
    ) -> UserMemoryFact | None:
        """Return one active fact owned by the user when present."""
        ...
