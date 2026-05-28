"""SQLAlchemy repository for durable user memory."""

from __future__ import annotations

from sqlalchemy import func, select, update

from icore_agent.application.usage.policy import current_timestamp
from icore_agent.domain.memory import UserMemoryFact, UserMemoryProfile

from ..sqlalchemy.sync_session import sync_session_scope
from .models import UserMemoryFactRecord, UserMemoryProfileRecord


class SqlAlchemyUserMemoryRepository:
    """Persist user memory profiles and facts through sync SQLAlchemy sessions."""

    def get_or_create_profile(self, user_id: str) -> UserMemoryProfile:
        """Load one user memory profile, creating an empty row when missing."""
        with sync_session_scope() as session:
            row = session.get(UserMemoryProfileRecord, user_id)
            if row is None:
                now = current_timestamp()
                row = UserMemoryProfileRecord(
                    user_id=user_id,
                    profile={},
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
                session.flush()
            return _to_profile(row)

    def save_profile(self, profile: UserMemoryProfile) -> UserMemoryProfile:
        """Persist profile counters and stable preference keys."""
        with sync_session_scope() as session:
            row = session.get(UserMemoryProfileRecord, profile.user_id)
            if row is None:
                row = UserMemoryProfileRecord(
                    user_id=profile.user_id,
                    created_at=profile.created_at or current_timestamp(),
                )
                session.add(row)
            row.profile = dict(profile.profile or {})
            row.maintenance_version = int(profile.maintenance_version)
            row.extract_count = int(profile.extract_count)
            row.turns_since_extract = int(profile.turns_since_extract)
            row.last_maintained_at = int(profile.last_maintained_at)
            row.updated_at = profile.updated_at or current_timestamp()
            session.flush()
            return _to_profile(row)

    def list_active_facts(self, user_id: str) -> list[UserMemoryFact]:
        """Return active facts for one user ordered by recency."""
        with sync_session_scope() as session:
            result = session.execute(
                select(UserMemoryFactRecord)
                .where(
                    UserMemoryFactRecord.user_id == user_id,
                    UserMemoryFactRecord.status == "active",
                )
                .order_by(UserMemoryFactRecord.last_confirmed_at.desc())
            )
            return [_to_fact(row) for row in result.scalars().all()]

    def find_active_fact(
        self,
        user_id: str,
        category: str,
        key: str,
    ) -> UserMemoryFact | None:
        """Return one active fact by category and key when present."""
        matches = self.list_active_facts_for_slot(user_id, category, key)
        return matches[0] if matches else None

    def list_active_facts_for_slot(
        self,
        user_id: str,
        category: str,
        key: str,
    ) -> list[UserMemoryFact]:
        """Return active facts for one category/key slot."""
        with sync_session_scope() as session:
            result = session.execute(
                select(UserMemoryFactRecord)
                .where(
                    UserMemoryFactRecord.user_id == user_id,
                    UserMemoryFactRecord.category == category,
                    UserMemoryFactRecord.key == key,
                    UserMemoryFactRecord.status == "active",
                )
                .order_by(UserMemoryFactRecord.last_confirmed_at.desc())
            )
            return [_to_fact(row) for row in result.scalars().all()]

    def save_fact(self, fact: UserMemoryFact) -> UserMemoryFact:
        """Insert or update one memory fact row."""
        with sync_session_scope() as session:
            row = None
            if fact.id is not None:
                row = session.get(UserMemoryFactRecord, fact.id)
            if row is None:
                now = current_timestamp()
                row = UserMemoryFactRecord(
                    user_id=fact.user_id,
                    category=fact.category,
                    key=fact.key,
                    value=fact.value,
                    created_at=fact.created_at or now,
                )
                session.add(row)
            row.category = fact.category
            row.key = fact.key
            row.value = fact.value
            row.status = fact.status
            row.source = fact.source
            row.confidence = float(fact.confidence)
            row.salience = float(fact.salience)
            row.access_count = int(fact.access_count)
            row.last_accessed_at = int(fact.last_accessed_at)
            row.last_confirmed_at = int(fact.last_confirmed_at)
            row.expires_at = fact.expires_at
            row.supersedes_id = fact.supersedes_id
            row.source_session_id = fact.source_session_id
            row.updated_at = fact.updated_at or current_timestamp()
            session.flush()
            return _to_fact(row)

    def count_active_facts(self, user_id: str) -> int:
        """Return how many active facts a user currently has."""
        with sync_session_scope() as session:
            result = session.execute(
                select(func.count())
                .select_from(UserMemoryFactRecord)
                .where(
                    UserMemoryFactRecord.user_id == user_id,
                    UserMemoryFactRecord.status == "active",
                )
            )
            return int(result.scalar_one())

    def mark_facts_accessed(self, fact_ids: list[int], *, accessed_at: int) -> None:
        """Increment access counters for facts injected into a turn."""
        if not fact_ids:
            return
        with sync_session_scope() as session:
            session.execute(
                update(UserMemoryFactRecord)
                .where(UserMemoryFactRecord.id.in_(fact_ids))
                .values(
                    access_count=UserMemoryFactRecord.access_count + 1,
                    last_accessed_at=accessed_at,
                    updated_at=accessed_at,
                )
            )


    def get_active_fact_by_id(
        self,
        user_id: str,
        fact_id: int,
    ) -> UserMemoryFact | None:
        """Return one active fact owned by the user when present."""
        with sync_session_scope() as session:
            row = session.get(UserMemoryFactRecord, fact_id)
            if row is None or row.user_id != user_id or row.status != "active":
                return None
            return _to_fact(row)


def _to_profile(row: UserMemoryProfileRecord | None) -> UserMemoryProfile:
    """Convert one ORM profile row into a domain profile."""
    if row is None:
        raise ValueError("profile row is required")
    return UserMemoryProfile(
        user_id=row.user_id,
        profile=dict(row.profile or {}),
        maintenance_version=int(row.maintenance_version),
        extract_count=int(row.extract_count),
        turns_since_extract=int(row.turns_since_extract),
        last_maintained_at=int(row.last_maintained_at),
        created_at=int(row.created_at),
        updated_at=int(row.updated_at),
    )


def _to_fact(row: UserMemoryFactRecord | None) -> UserMemoryFact | None:
    """Convert one ORM fact row into a domain fact."""
    if row is None:
        return None
    return UserMemoryFact(
        id=int(row.id),
        user_id=row.user_id,
        category=row.category,
        key=row.key,
        value=row.value,
        status=row.status,
        source=row.source,
        confidence=float(row.confidence),
        salience=float(row.salience),
        access_count=int(row.access_count),
        last_accessed_at=int(row.last_accessed_at),
        last_confirmed_at=int(row.last_confirmed_at),
        expires_at=row.expires_at,
        supersedes_id=row.supersedes_id,
        source_session_id=row.source_session_id,
        created_at=int(row.created_at),
        updated_at=int(row.updated_at),
    )
