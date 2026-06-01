from __future__ import annotations

from uuid import uuid4

from icore_agent.application.usage.policy import default_usage
from icore_agent.domain.account.plans import Plan
from icore_agent.domain.user import UserProfile
from icore_agent.infrastructure.persistence.sqlalchemy.sync_session import (
    ensure_user_schema,
    sync_session_scope,
)
from icore_agent.infrastructure.persistence.users.sqlalchemy_repository import (
    SqlAlchemyUserRepository,
)


def test_sqlalchemy_user_repository_persists_user_profile():
    """Verify the concrete repository stores and loads domain user profiles."""
    ensure_user_schema()
    email = f"trial-{uuid4().hex[:8]}@example.com"
    public_id = str(uuid4())
    with sync_session_scope() as session:
        repo = SqlAlchemyUserRepository(session)
        saved = repo.save(
            UserProfile(
                public_id=public_id,
                email=email,
                name="Trial User",
                plan=Plan.TRIAL.value,
                plan_label=Plan.TRIAL.limits.label,
                organization_id="org_test",
                organization_name="Trial Team",
                roles=["owner"],
                byok={},
                usage=default_usage(),
                created_at=123,
                updated_at=123,
            )
        )
        loaded = repo.get_by_email(email)

    assert loaded is not None
    assert loaded.public_id == saved.public_id
    assert loaded.email == email
    assert loaded.plan == "trial"
    assert loaded.plan_label == Plan.TRIAL.limits.label
    assert loaded.organization_id == "org_test"


def test_sqlalchemy_user_repository_email_exists_uses_indexed_lookup():
    """Verify email existence checks do not require loading full user rows."""
    ensure_user_schema()
    email = f"trial-{uuid4().hex[:8]}@example.com"
    missing = f"missing-{uuid4().hex[:8]}@example.com"
    public_id = str(uuid4())
    with sync_session_scope() as session:
        repo = SqlAlchemyUserRepository(session)
        repo.save(
            UserProfile(
                public_id=public_id,
                email=email,
                name="Trial User",
                plan=Plan.TRIAL.value,
                plan_label=Plan.TRIAL.limits.label,
                organization_id="org_test",
                organization_name="Trial Team",
                roles=["owner"],
                byok={},
                usage=default_usage(),
                created_at=123,
                updated_at=123,
            )
        )
        assert repo.email_exists(email) is True
        assert repo.email_exists(email.upper()) is True
        assert repo.email_exists(missing) is False
