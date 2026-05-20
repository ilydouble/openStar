from __future__ import annotations

from icore_agent.control_plane.constants import PLAN_LIMITS
from icore_agent.database.sync_session import ensure_user_schema, sync_session_scope
from icore_agent.users.repository import UserRepository


def test_user_repository_persists_trial_account():
    ensure_user_schema()
    with sync_session_scope() as session:
        repo = UserRepository(session)
        user = repo.create_trial_user(
            name="Trial User",
            email="trial@example.com",
            organization_id="org_test",
            organization_name="Trial Team",
        )
        loaded = repo.get_by_email("trial@example.com")
        assert loaded is not None
        assert loaded.public_id == user.public_id
        payload = repo.to_api_dict(loaded)
        assert payload["email"] == "trial@example.com"
        assert payload["plan"] == "free"
        assert payload["plan_label"] == PLAN_LIMITS["free"]["label"]
        assert payload["organization_id"] == "org_test"


def test_user_repository_tracks_message_quota():
    ensure_user_schema()
    with sync_session_scope() as session:
        repo = UserRepository(session)
        user = repo.create_trial_user(
            name="Quota User",
            email="quota@example.com",
            organization_id="org_quota",
            organization_name="Quota Team",
        )
        allowed, reason = repo.check_quota(user, "messages")
        assert allowed is True
        assert reason is None
        for _ in range(PLAN_LIMITS["free"]["message_limit"]):
            repo.consume_quota(user, "messages")
        allowed, reason = repo.check_quota(user, "messages")
        assert allowed is False
        assert reason == "messages quota exceeded for free"
