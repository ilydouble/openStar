from __future__ import annotations

from icore_agent.application.usage.policy import default_usage, quota_period_start
from icore_agent.application.usage.service import UsageService
from icore_agent.domain.account.plans import Plan
from icore_agent.domain.user import UserProfile


def _user_profile(user_id: str = "u1") -> UserProfile:
    """Create a user profile with an active quota period for usage tests."""
    usage = default_usage()
    usage["quota_period_start"] = quota_period_start()
    return UserProfile(
        public_id=user_id,
        email=f"{user_id}@example.com",
        name="Usage User",
        plan=Plan.FREE.value,
        plan_label=Plan.FREE.limits.label,
        roles=["owner"],
        byok={},
        usage=usage,
        created_at=1,
        updated_at=1,
    )


class FakeUsageStore:
    """Usage store double that records service persistence calls."""

    def __init__(self, user: UserProfile) -> None:
        """Create the fake store with one persisted user."""
        self.users = {user.public_id: user}
        self.payload = None

    def get_user_by_id(self, user_id: str) -> UserProfile | None:
        """Return one stored user."""
        return self.users.get(user_id)

    def save_user(self, user: UserProfile) -> UserProfile:
        """Persist a changed user profile in memory."""
        self.users[user.public_id] = user
        return user

    def list_users(self) -> list[UserProfile]:
        """Return all in-memory users."""
        return list(self.users.values())

    def record_usage_event(self, **payload) -> None:
        """Capture the usage event payload."""
        self.payload = payload

    def usage_summary(self, user_id: str) -> dict:
        """Return a small usage summary for the requested user."""
        return {"user_id": user_id}

    def admin_overview(self, users: list[UserProfile]) -> dict:
        """Return a small admin overview for the provided users."""
        return {"users": {"total": len(users)}}


def test_usage_service_records_token_metrics_with_cost():
    """Verify LLM events are persisted and token quota counters are updated."""
    store = FakeUsageStore(_user_profile())
    service = UsageService(store)

    service.record_llm_usage(
        user_id="u1",
        session_id="s1",
        model="demo-model",
        prompt_tokens=120,
        completion_tokens=30,
        total_tokens=150,
    )

    assert store.payload == {
        "user_id": "u1",
        "session_id": "s1",
        "model": "demo-model",
        "prompt_tokens": 120,
        "completion_tokens": 30,
        "total_tokens": 150,
        "estimated_cost": 0.0003,
    }
    assert store.users["u1"].usage["token_count"] == 150


def test_usage_service_owns_message_quota_policy():
    """Verify message quota decisions live in the usage application service."""
    store = FakeUsageStore(_user_profile())
    service = UsageService(store)

    allowed, reason = service.check_quota("u1", "messages")
    assert (allowed, reason) == (True, None)

    for _ in range(Plan.FREE.limits.message_limit):
        service.consume_quota("u1", "messages")

    allowed, reason = service.check_quota("u1", "messages")
    assert allowed is False
    assert reason == "messages quota exceeded for free"
