from __future__ import annotations

from icore_agent.application.usage.policy import (
    default_usage,
    ensure_current_usage,
    quota_period_start,
)
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
        plan=Plan.TRIAL.value,
        plan_label=Plan.TRIAL.limits.label,
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


def test_usage_service_does_not_cap_messages():
    """Verify message counts are not treated as a hard chat quota."""
    store = FakeUsageStore(_user_profile())
    service = UsageService(store)

    allowed, reason = service.check_quota("u1", "messages")
    assert (allowed, reason) == (True, None)

    for _ in range(10):
        service.consume_quota("u1", "messages")

    allowed, reason = service.check_quota("u1", "messages")
    assert (allowed, reason) == (True, None)
    assert store.users["u1"].usage["message_count"] == 10


# ---------------------------------------------------------------------------
# TRIAL plan — one-time lifetime quota, must never reset monthly
# ---------------------------------------------------------------------------

def _trial_user(user_id: str = "t1", token_count: int = 0) -> UserProfile:
    """Create a TRIAL user whose quota period started in a past month."""
    # Set quota_period_start to January 2024 so should_reset_quota() would
    # return True for any FREE/TEAM/ENTERPRISE user — but NOT for TRIAL.
    stale_period = 1704067200  # 2024-01-01 00:00:00 UTC
    usage = default_usage()
    usage["quota_period_start"] = stale_period
    usage["token_count"] = token_count
    return UserProfile(
        public_id=user_id,
        email=f"{user_id}@example.com",
        name="Trial User",
        plan=Plan.TRIAL.value,
        plan_label=Plan.TRIAL.limits.label,
        roles=["owner"],
        byok={},
        usage=usage,
        created_at=1,
        updated_at=1,
    )


def test_trial_usage_is_never_reset_monthly():
    """TRIAL counters must survive a month boundary — quota is one-time."""
    user = _trial_user(token_count=49_000)
    result_user, usage, should_save = ensure_current_usage(user)
    # should_save may be False (no reset triggered) or True only if usage was
    # missing entirely — but the token count must never be zeroed out.
    assert usage["token_count"] == 49_000, (
        "TRIAL token_count must not be reset at a month boundary"
    )


def test_trial_quota_blocks_after_limit():
    """TRIAL user who exhausted 50K tokens must be denied further chat."""
    store = FakeUsageStore(_trial_user(token_count=50_000))
    service = UsageService(store)
    allowed, reason = service.check_quota("t1", "tokens")
    assert allowed is False
    assert reason is not None


def test_trial_quota_allows_before_limit():
    """TRIAL user with remaining tokens must be permitted to continue."""
    store = FakeUsageStore(_trial_user(token_count=10_000))
    service = UsageService(store)
    allowed, reason = service.check_quota("t1", "tokens")
    assert (allowed, reason) == (True, None)


def test_paid_plan_quota_resets_on_new_month():
    """Paid plans (TEAM/ENTERPRISE) must reset counters when the quota period is stale."""
    stale_period = 1704067200  # 2024-01-01 UTC — always in the past
    usage = default_usage()
    usage["quota_period_start"] = stale_period
    usage["token_count"] = 500_000
    user = UserProfile(
        public_id="p1",
        email="p1@example.com",
        name="Team User",
        plan=Plan.TEAM.value,
        plan_label=Plan.TEAM.limits.label,
        roles=["owner"],
        byok={},
        usage=usage,
        created_at=1,
        updated_at=1,
    )
    _, refreshed_usage, should_save = ensure_current_usage(user)
    assert should_save is True, "TEAM usage should be persisted after monthly reset"
    assert refreshed_usage["token_count"] == 0, (
        "TEAM token_count must be zeroed at the start of a new month"
    )
