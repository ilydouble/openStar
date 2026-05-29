from __future__ import annotations

import pytest

from icore_agent.application.memory import UserMemoryService
from icore_agent.application.usage.policy import current_timestamp, default_usage
from icore_agent.domain.account.plans import Plan
from icore_agent.domain.memory import UserMemoryFact
from icore_agent.domain.user import UserProfile
from icore_agent.infrastructure.persistence.memory import SqlAlchemyUserMemoryRepository
from icore_agent.infrastructure.persistence.sqlalchemy.sync_session import (
    ensure_user_schema,
    reset_sync_engine,
    sync_session_scope,
)
from icore_agent.infrastructure.persistence.users.sqlalchemy_repository import (
    SqlAlchemyUserRepository,
)


@pytest.fixture()
def memory_repository(tmp_path, monkeypatch) -> SqlAlchemyUserMemoryRepository:
    """Create an isolated sqlite-backed user memory repository."""
    db_path = tmp_path / "account-memory.sqlite3"
    monkeypatch.setenv("ICORE_TEST_SYNC_DATABASE_URL",
                       f"sqlite+pysqlite:///{db_path}")
    reset_sync_engine()
    ensure_user_schema()
    with sync_session_scope() as session:
        users = SqlAlchemyUserRepository(session)
        users.save(
            UserProfile(
                public_id="u1",
                email="u1@example.com",
                name="Memory User",
                plan=Plan.TRIAL.value,
                plan_label=Plan.TRIAL.limits.label,
                roles=["owner"],
                byok={},
                usage=default_usage(),
                created_at=current_timestamp(),
                updated_at=current_timestamp(),
            )
        )
    return SqlAlchemyUserMemoryRepository()


def test_list_account_memory_returns_active_facts(memory_repository) -> None:
    """Account memory listing should expose active facts and profile keys."""
    now = current_timestamp()
    memory_repository.save_fact(UserMemoryFact(
        user_id="u1",
        category="personal",
        key="name",
        value="Alex",
        source="explicit",
        confidence=0.95,
        salience=0.9,
        last_confirmed_at=now,
        created_at=now,
        updated_at=now,
    ))
    service = UserMemoryService(memory_repository)

    payload = service.list_account_memory("u1")

    assert payload["profile"] == {}
    assert len(payload["facts"]) == 1
    assert payload["facts"][0]["key"] == "name"
    assert payload["facts"][0]["value"] == "Alex"


def test_update_fact_value_updates_owned_fact(memory_repository) -> None:
    """Users should be able to edit one owned fact value."""
    now = current_timestamp()
    saved = memory_repository.save_fact(UserMemoryFact(
        user_id="u1",
        category="personal",
        key="location",
        value="US",
        source="inferred",
        confidence=0.7,
        salience=0.6,
        last_confirmed_at=now,
        created_at=now,
        updated_at=now,
    ))
    service = UserMemoryService(memory_repository)

    updated = service.update_fact_value("u1", int(saved.id), "United States")

    assert updated["value"] == "United States"
    assert updated["source"] == "explicit"
    active = memory_repository.list_active_facts("u1")
    assert active[0].value == "United States"


def test_delete_fact_soft_deletes_owned_fact(memory_repository) -> None:
    """Deleting one fact should remove it from active listings."""
    now = current_timestamp()
    saved = memory_repository.save_fact(UserMemoryFact(
        user_id="u1",
        category="goal",
        key="launch_date",
        value="Q3",
        source="explicit",
        confidence=0.8,
        salience=0.7,
        last_confirmed_at=now,
        created_at=now,
        updated_at=now,
    ))
    service = UserMemoryService(memory_repository)

    service.delete_fact("u1", int(saved.id))

    assert memory_repository.list_active_facts("u1") == []


def test_update_fact_value_rejects_other_users_fact(memory_repository) -> None:
    """Fact updates must be scoped to the owning user."""
    now = current_timestamp()
    saved = memory_repository.save_fact(UserMemoryFact(
        user_id="u1",
        category="personal",
        key="name",
        value="Alex",
        source="explicit",
        confidence=0.9,
        salience=0.8,
        last_confirmed_at=now,
        created_at=now,
        updated_at=now,
    ))
    service = UserMemoryService(memory_repository)

    with pytest.raises(LookupError):
        service.update_fact_value("u2", int(saved.id), "Sam")
