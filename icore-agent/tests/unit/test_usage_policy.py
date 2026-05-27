"""Tests for usage analytics and LiteLLM recording helpers."""

from __future__ import annotations

from icore_agent.application.usage.policy import (
    admin_usage_overview,
    consume_quota,
    plan_usage_analytics,
    usage_key,
)
from icore_agent.application.usage.recording import (
    active_turn_usage_events,
    begin_turn_usage_capture,
    build_litellm_usage_event,
    end_turn_usage_capture,
    flush_turn_usage_capture,
    resolve_litellm_user_id,
)
from icore_agent.domain.account.plans import Plan
from icore_agent.domain.user import UserProfile


def test_usage_key_maps_v2_quota_resources():
    """Quota resource names must map to the v2 usage counter keys."""
    assert usage_key("tasks") == "task_count"
    assert usage_key("tokens") == "token_count"
    assert usage_key("attachments") == "attachment_count"


def test_consume_quota_increments_attachment_count():
    """Attachment consumption must update attachment_count, not token_count."""
    user = UserProfile(
        public_id="u1",
        email="one@example.com",
        name="One",
        plan=Plan.TRIAL.value,
        plan_label=Plan.TRIAL.limits.label,
        roles=["owner"],
        byok={},
        usage={"task_count": 0, "token_count": 0, "attachment_count": 1},
        created_at=1,
        updated_at=1,
    )

    updated = consume_quota(user, user.usage, "attachments", 2)

    assert updated.usage["attachment_count"] == 3
    assert updated.usage["token_count"] == 0


def test_plan_usage_analytics_does_not_synthesize_legacy_unknown_model() -> None:
    """Analytics should stay empty when only token counters exist without call metadata."""
    analytics = plan_usage_analytics(
        {
            "token_count": 1296,
            "message_count": 16,
            "image_count": 3,
            "attachment_count": 0,
            "quota_period_start": 1777593600,
        }
    )

    assert analytics["model_calls"] == 0
    assert analytics["active_models"] == 0
    assert analytics["by_model"] == {}
    assert analytics["estimated_cost"] == 0.002592


def test_plan_usage_analytics_aggregates_persisted_model_stats() -> None:
    """Per-model analytics should reflect stored usage metadata only."""
    analytics = plan_usage_analytics(
        {
            "token_count": 150,
            "llm_call_count": 1,
            "models_used": ["zai/glm-4.7"],
            "by_model": {
                "zai/glm-4.7": {
                    "calls": 1,
                    "tokens": 150,
                    "cost": 0.0003,
                }
            },
        }
    )

    assert analytics["model_calls"] == 1
    assert analytics["active_models"] == 1
    assert analytics["by_model"]["zai/glm-4.7"]["tokens"] == 150
    assert analytics["estimated_cost"] == 0.0003


def test_admin_usage_overview_aggregates_postgres_profiles() -> None:
    """Admin overview totals should come from PostgreSQL usage counters."""
    users = [
        UserProfile(
            public_id="u1",
            email="one@example.com",
            name="One",
            plan=Plan.TEAM.value,
            plan_label=Plan.TEAM.limits.label,
            roles=["owner"],
            byok={},
            usage={
                "token_count": 100,
                "message_count": 2,
                "llm_call_count": 1,
                "by_model": {
                    "zai/glm-4.7": {"calls": 1, "tokens": 100, "cost": 0.0002},
                },
            },
            created_at=1,
            updated_at=999_999_999,
        )
    ]

    overview = admin_usage_overview(
        users,
        new_trials_7d=0,
        leads={"total": 0, "enterprise": 0, "demo": 0},
    )

    assert overview["usage"]["total_tokens"] == 100
    assert overview["usage"]["total_cost"] == 0.0002
    assert overview["usage"]["total_calls"] == 1
    assert overview["heavy_users"][0]["email"] == "one@example.com"


def test_resolve_litellm_user_id_prefers_metadata_over_runtime_context() -> None:
    """LiteLLM callbacks should attribute usage to metadata user ids when present."""
    resolved = resolve_litellm_user_id(
        {"metadata": {"user_id": "user-from-metadata", "session_id": "s1"}}
    )

    assert resolved == "user-from-metadata"


def test_build_litellm_usage_event_falls_back_to_token_counter(monkeypatch) -> None:
    """Usage extraction should estimate tokens when providers omit usage metadata."""

    def fake_token_counter(*, model: str, messages=None, text: str = ""):
        if messages:
            return 30
        if text:
            return 12
        return 0

    monkeypatch.setitem(
        __import__("sys").modules,
        "litellm",
        type("LiteLLMStub", (), {"token_counter": staticmethod(fake_token_counter)}),
    )

    response = type(
        "Response",
        (),
        {
            "usage": None,
            "choices": [
                type(
                    "Choice",
                    (),
                    {"message": type("Message", (), {"content": "world"})()},
                )()
            ],
        },
    )()
    event = build_litellm_usage_event(
        {"model": "zai/glm-4.7", "messages": [{"role": "user", "content": "hello"}]},
        response,
    )

    assert event is not None
    assert event["prompt_tokens"] == 30
    assert event["completion_tokens"] == 12
    assert event["total_tokens"] == 42


def test_flush_turn_usage_capture_persists_buffered_events() -> None:
    """Buffered chat-turn usage should flush through the usage service recorder."""
    capture_token = begin_turn_usage_capture()
    bucket = active_turn_usage_events()
    assert bucket is not None
    bucket.append(
        {
            "session_id": "session-1",
            "model": "zai/glm-4.7",
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        }
    )
    recorded: list[dict[str, object]] = []

    def _record(**payload):
        recorded.append(payload)

    count = flush_turn_usage_capture(
        user_id="user-1",
        session_id="session-1",
        record_usage=_record,
    )
    end_turn_usage_capture(capture_token)

    assert count == 1
    assert recorded[0]["user_id"] == "user-1"
    assert recorded[0]["total_tokens"] == 15
