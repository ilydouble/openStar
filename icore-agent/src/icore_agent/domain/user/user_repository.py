"""Abstract user repository contract."""

from __future__ import annotations

from typing import Protocol

from .models import UserProfile


class UserRepository(Protocol):
    """Persistence boundary for account profiles."""

    def get_by_public_id(self, public_id: str) -> UserProfile | None:
        """Load a user profile by public id."""
        ...

    def get_by_email(self, email: str) -> UserProfile | None:
        """Load a user profile by email address."""
        ...

    def list_all(self) -> list[UserProfile]:
        """Return every user profile."""
        ...

    def save(self, user: UserProfile) -> UserProfile:
        """Insert or update one user profile."""
        ...
