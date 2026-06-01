from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from icore_agent.application.usage.policy import quota_period_start
from icore_agent.domain.account.plans import Plan
from icore_agent.domain.user import UserProfile
from icore_agent.infrastructure.persistence.users.postgres_repositories import (
    PostgresBillingSummaryRepository,
)


def _user() -> UserProfile:
    """Create a trial user profile with v2 usage counters for billing summary tests."""
    return UserProfile(
        public_id="u1",
        email="trial@example.com",
        name="Trial User",
        plan=Plan.TRIAL.value,
        plan_label=Plan.TRIAL.limits.label,
        roles=["owner"],
        byok={},
        usage={
            "task_count": 3,
            "token_count": 1200,
            "attachment_count": 1,
            "quota_period_start": quota_period_start(),
        },
        created_at=1,
        updated_at=1,
    )


def test_get_plan_summary_returns_v2_quota_shape():
    """Verify billing plan summaries expose task-based limits and usage counters."""
    user = _user()
    repo_mock = MagicMock()
    repo_mock.get_by_public_id.return_value = user
    repo_mock.save.return_value = user
    session = MagicMock()

    @contextmanager
    def fake_scope():
        yield session

    with patch(
        "icore_agent.infrastructure.persistence.users.postgres_repositories.sync_session_scope",
        fake_scope,
    ), patch(
        "icore_agent.infrastructure.persistence.users.postgres_repositories.SqlAlchemyUserRepository",
        return_value=repo_mock,
    ):
        summary = PostgresBillingSummaryRepository(
            store=MagicMock()).get_plan_summary("u1")

    assert summary["plan"] == "trial"
    assert summary["limits"] == {"tasks": 10, "attachments": 10}
    assert summary["usage"]["tasks"] == 3
    assert summary["usage"]["tokens"] == 1200
    assert summary["usage"]["attachments"] == 1
    assert "messages" not in summary["limits"]
    assert "messages" not in summary["usage"]
