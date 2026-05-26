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


def test_record_llm_usage_persists_cost_event_and_tracks_tokens():
    """LLM events must be persisted and the internal token counter updated."""
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
    # token_count is updated for cost reporting but does NOT gate further calls.
    assert store.users["u1"].usage["token_count"] == 150
    assert store.users["u1"].usage["llm_call_count"] == 1
    assert store.users["u1"].usage["by_model"]["demo-model"]["calls"] == 1


def test_token_spend_never_blocks_a_request():
    """Tokens are cost-tracking only — high token counts must not deny tasks."""
    store = FakeUsageStore(_user_profile())
    service = UsageService(store)

    # Simulate heavy token use without consuming any tasks.
    service.record_llm_usage(
        user_id="u1", session_id="s1", model="m",
        prompt_tokens=100_000, completion_tokens=50_000, total_tokens=150_000,
    )

    # Task quota check must still pass (TRIAL has 10 tasks, 0 used so far).
    allowed, reason = service.check_quota("u1", "tasks")
    assert (allowed, reason) == (True, None)


# ---------------------------------------------------------------------------
# Task quota — the primary user-visible quota unit
# ---------------------------------------------------------------------------

def _trial_user(user_id: str = "t1", task_count: int = 0) -> UserProfile:
    """Create a TRIAL user with a given number of tasks already consumed."""
    usage = default_usage()
    usage["quota_period_start"] = quota_period_start()
    usage["task_count"] = task_count
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


def test_task_quota_blocks_when_monthly_limit_reached():
    """Users who exhaust their monthly task quota must be denied."""
    store = FakeUsageStore(_trial_user(task_count=10))  # TRIAL limit = 10
    service = UsageService(store)
    allowed, reason = service.check_quota("t1", "tasks")
    assert allowed is False
    assert reason is not None


def test_task_quota_allows_when_under_limit():
    """Users with remaining tasks must be permitted to continue."""
    store = FakeUsageStore(_trial_user(task_count=5))
    service = UsageService(store)
    allowed, reason = service.check_quota("t1", "tasks")
    assert (allowed, reason) == (True, None)


def test_consume_task_increments_task_count():
    """consume_task must deduct exactly one task from the user's quota."""
    store = FakeUsageStore(_trial_user(task_count=3))
    service = UsageService(store)
    service.consume_task("t1")
    assert store.users["t1"].usage["task_count"] == 4


def test_byok_task_quota_is_unlimited():
    """BYOK users must never be blocked regardless of task count."""
    usage = default_usage()
    usage["quota_period_start"] = quota_period_start()
    usage["task_count"] = 999_999
    user = UserProfile(
        public_id="b1", email="b1@example.com", name="BYOK User",
        plan=Plan.BYOK.value, plan_label=Plan.BYOK.limits.label,
        roles=["owner"], byok={}, usage=usage, created_at=1, updated_at=1,
    )
    store = FakeUsageStore(user)
    service = UsageService(store)
    allowed, reason = service.check_quota("b1", "tasks")
    assert (allowed, reason) == (True, None)


# ---------------------------------------------------------------------------
# Monthly reset — ALL plans now reset at the start of each month
# ---------------------------------------------------------------------------

def _stale_user(plan: Plan, task_count: int = 5) -> UserProfile:
    """Create a user whose quota period started in a past month."""
    stale_period = 1704067200  # 2024-01-01 UTC — always in the past
    usage = default_usage()
    usage["quota_period_start"] = stale_period
    usage["task_count"] = task_count
    return UserProfile(
        public_id="s1", email="s1@example.com", name="Stale User",
        plan=plan.value, plan_label=plan.limits.label,
        roles=["owner"], byok={}, usage=usage, created_at=1, updated_at=1,
    )


def test_all_plans_reset_task_count_monthly():
    """Every plan tier — including Trial — resets task_count at month start."""
    for plan in (Plan.TRIAL, Plan.PRO, Plan.TEAM, Plan.PREMIUM):
        user = _stale_user(plan, task_count=50)
        _, refreshed_usage, should_save = ensure_current_usage(user)
        assert should_save is True, f"{plan.value}: stale period must trigger save"
        assert refreshed_usage["task_count"] == 0, (
            f"{plan.value}: task_count must be zeroed at new month"
        )
