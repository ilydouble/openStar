"""SQLAlchemy implementation of the user repository contract."""

from __future__ import annotations

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from icore_agent.contexts.account.domain.user import UserProfile

from .models import User


class SqlAlchemyUserRepository:
    """Persist account profiles through a SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to one transactional SQLAlchemy session."""
        self._session = session

    def get_by_public_id(self, public_id: str) -> UserProfile | None:
        """Load a user profile by public id."""
        result = self._session.execute(
            select(User).where(User.public_id == public_id)
        )
        return _to_profile(result.scalar_one_or_none())

    def get_by_email(self, email: str) -> UserProfile | None:
        """Load a user profile by normalized email address."""
        normalized = email.strip().lower()
        result = self._session.execute(
            select(User).where(User.email == normalized)
        )
        return _to_profile(result.scalar_one_or_none())

    def email_exists(self, email: str) -> bool:
        """Return whether a normalized email is registered (indexed lookup only)."""
        normalized = email.strip().lower()
        return bool(
            self._session.scalar(
                select(exists().where(User.email == normalized))
            )
        )

    def list_all(self) -> list[UserProfile]:
        """Return every persisted account profile."""
        result = self._session.execute(
            select(User).order_by(User.created_at.asc()))
        return [_to_profile(user) for user in result.scalars().all()]

    def save(self, user: UserProfile) -> UserProfile:
        """Insert or update one user profile."""
        row = self._find_row(user.public_id, user.email)
        if row is None:
            row = User(
                public_id=user.public_id,
                user_name=user.email,
                password_hash="",
                email=user.email,
                name=user.name,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
            self._session.add(row)
        row.user_name = user.email
        row.email = user.email
        row.name = user.name
        row.plan = user.plan
        row.plan_label = user.plan_label
        row.organization_id = user.organization_id
        row.organization_name = user.organization_name
        row.roles = list(user.roles or ["owner"])
        row.byok = dict(user.byok or {})
        row.usage = dict(user.usage or {})
        row.created_at = int(user.created_at)
        row.updated_at = int(user.updated_at)
        self._session.flush()
        return _to_profile(row)

    def _find_row(self, public_id: str, email: str) -> User | None:
        """Find an existing row by public id or email."""
        result = self._session.execute(
            select(User).where((User.public_id == public_id)
                               | (User.email == email))
        )
        return result.scalar_one_or_none()


def _to_profile(user: User | None) -> UserProfile | None:
    """Convert an ORM user row into a domain profile."""
    if user is None:
        return None
    return UserProfile(
        public_id=user.public_id,
        email=user.email,
        name=user.name,
        plan=user.plan,
        plan_label=user.plan_label,
        organization_id=user.organization_id,
        organization_name=user.organization_name,
        roles=list(user.roles or ["owner"]),
        byok=dict(user.byok or {}),
        usage=dict(user.usage or {}),
        created_at=int(user.created_at),
        updated_at=int(user.updated_at),
    )
