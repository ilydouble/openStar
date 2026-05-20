from __future__ import annotations

from icore_agent.application.usage.service import UsageService


class FakeUsageRepository:
    """Usage repository double that records the payload sent by the service."""

    def __init__(self) -> None:
        self.payload = None

    def record_usage_event(self, **payload) -> None:
        self.payload = payload


def test_usage_service_records_token_metrics_with_cost():
    repo = FakeUsageRepository()
    service = UsageService(repo)

    service.record_llm_usage(
        user_id="u1",
        session_id="s1",
        model="demo-model",
        prompt_tokens=120,
        completion_tokens=30,
        total_tokens=150,
    )

    assert repo.payload == {
        "user_id": "u1",
        "session_id": "s1",
        "model": "demo-model",
        "prompt_tokens": 120,
        "completion_tokens": 30,
        "total_tokens": 150,
        "estimated_cost": 0.0003,
    }
