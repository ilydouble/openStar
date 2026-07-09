from __future__ import annotations

import pytest

from icore_agent.contexts.agent.domain.prompt import build_base_instructions
from icore_agent.contexts.memory.application import UserMemoryService
from icore_agent.contexts.account.application.usage.policy import current_timestamp, default_usage
from icore_agent.contexts.account.domain.account.plans import Plan
from icore_agent.contexts.memory.domain import (
    MemoryExtractionResult,
    MemoryFactCandidate,
    TurnMemoryContext,
    UserMemoryFact,
)
from icore_agent.contexts.account.domain.user import UserProfile
from icore_agent.contexts.memory.infrastructure.persistence import SqlAlchemyUserMemoryRepository
from icore_agent.infrastructure.persistence.sqlalchemy.sync_session import (
    ensure_user_schema,
    reset_sync_engine,
    sync_session_scope,
)
from icore_agent.contexts.account.infrastructure.persistence.users.sqlalchemy_repository import (
    SqlAlchemyUserRepository,
)


@pytest.fixture()
def memory_repository(tmp_path, monkeypatch) -> SqlAlchemyUserMemoryRepository:
    """Create an isolated sqlite-backed user memory repository."""
    db_path = tmp_path / "memory.sqlite3"
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


def test_user_memory_service_injects_ranked_prompt(memory_repository) -> None:
    """Read path should inject profile and only relevant active facts."""
    repo = memory_repository
    now = current_timestamp()
    repo.save_fact(UserMemoryFact(
        user_id="u1",
        category="work_context",
        key="platform",
        value="Shopify operations",
        source="explicit",
        confidence=0.95,
        salience=0.9,
        last_confirmed_at=now,
        created_at=now,
        updated_at=now,
    ))
    repo.save_profile(repo.get_or_create_profile("u1"))
    service = UserMemoryService(repo)

    prompt = service.build_memory_prompt(
        "u1",
        TurnMemoryContext(
            message="Review my Shopify product page",
        ),
    )

    assert prompt is not None
    assert "Shopify operations" in prompt


def test_extract_phase_supersedes_conflicting_fact(memory_repository) -> None:
    """Extract phase should supersede an inferred fact with an explicit update."""
    repo = memory_repository
    now = current_timestamp()
    existing = repo.save_fact(UserMemoryFact(
        user_id="u1",
        category="work_context",
        key="platform",
        value="WooCommerce",
        source="inferred",
        confidence=0.6,
        salience=0.5,
        last_confirmed_at=now,
        created_at=now,
        updated_at=now,
    ))

    def _extract(**_: object) -> MemoryExtractionResult:
        return MemoryExtractionResult(
            profile_updates={"role": "seller"},
            candidates=(
                MemoryFactCandidate(
                    category="work_context",
                    key="platform",
                    value="Shopify",
                    source="explicit",
                    confidence=0.95,
                    salience=0.9,
                ),
            ),
        )

    service = UserMemoryService(repo, extractor=_extract)
    service.extract_from_session_sync(
        user_id="u1",
        session_id="session-1",
        session_summary="User said they run a Shopify store.",
        recent_messages=[
            {"role": "user", "content": "I run a Shopify store."},
            {"role": "assistant", "content": "Got it."},
        ],
    )

    active = repo.list_active_facts("u1")
    assert len(active) == 1
    assert active[0].value == "Shopify"
    assert active[0].source == "explicit"
    assert active[0].supersedes_id == existing.id


@pytest.mark.asyncio
async def test_extract_on_session_end_skips_empty_session(memory_repository) -> None:
    """Session-end extraction should no-op when there is nothing to extract."""
    service = UserMemoryService(memory_repository)

    await service.extract_on_session_end(
        user_id="u1",
        session_id="session-1",
        session_summary="",
        recent_messages=[],
    )

    profile = memory_repository.get_or_create_profile("u1")
    assert profile.extract_count == 0


def test_orchestrator_prompt_excludes_user_memory_section() -> None:
    """System prompt should not include runtime user memory context."""
    prompt = build_base_instructions()
    assert "## About this user" not in prompt
    assert "Session summary" not in prompt
