from __future__ import annotations

from uuid import uuid4

from icore_agent.application.usage.policy import default_usage
from icore_agent.domain.account.plans import Plan
from icore_agent.domain.user import UserProfile
from icore_agent.infrastructure.persistence.payment_events import (
    PostgresPaymentEventRepository,
)
from icore_agent.infrastructure.persistence.sqlalchemy.sync_session import (
    ensure_user_schema,
    sync_session_scope,
)
from icore_agent.infrastructure.persistence.users.sqlalchemy_repository import (
    SqlAlchemyUserRepository,
)


class RecordingStore:
    """Capture control-plane events emitted by payment event processing."""

    def __init__(self) -> None:
        """Create an empty event recorder."""
        self.events: list[tuple[str, dict]] = []

    def append_event(self, event_type: str, **payload) -> None:
        """Record one emitted event."""
        self.events.append((event_type, payload))


def test_payment_succeeded_event_upgrades_plan_once() -> None:
    """Payment success events must apply entitlements exactly once."""
    ensure_user_schema()
    public_id = str(uuid4())
    store = RecordingStore()
    _create_user(public_id, byok={"enabled": True, "api_key": "keep-me"})

    repo = PostgresPaymentEventRepository(store)
    payload = _payment_succeeded_payload(
        event_id="evt-payment-success-1",
        user_id=public_id,
        plan_code="pro",
    )

    first = repo.apply_payment_succeeded(payload)
    second = repo.apply_payment_succeeded(payload)

    assert first.status == "applied"
    assert second.status == "duplicate"
    with sync_session_scope() as session:
        user = SqlAlchemyUserRepository(session).get_by_public_id(public_id)

    assert user is not None
    assert user.plan == Plan.PRO.value
    assert user.plan_label == Plan.PRO.limits.label
    assert user.byok == {"enabled": True, "api_key": "keep-me"}
    assert store.events == [
        (
            "payment_plan_applied",
            {
                "user_id": public_id,
                "old_plan": Plan.TRIAL.value,
                "new_plan": Plan.PRO.value,
                "event_id": "evt-payment-success-1",
                "order_id": "11111111-1111-7111-8111-111111111111",
                "order_no": "wx202606041200000000000001",
            },
        )
    ]


def test_payment_succeeded_event_rejects_unknown_plan() -> None:
    """Payment events must not write unknown plan codes into account state."""
    ensure_user_schema()
    public_id = str(uuid4())
    _create_user(public_id)

    repo = PostgresPaymentEventRepository(RecordingStore())
    payload = _payment_succeeded_payload(
        event_id="evt-payment-success-2",
        user_id=public_id,
        plan_code="enterprise",
    )

    result = repo.apply_payment_succeeded(payload)

    assert result.status == "rejected"
    assert "unsupported plan" in result.reason
    with sync_session_scope() as session:
        user = SqlAlchemyUserRepository(session).get_by_public_id(public_id)

    assert user is not None
    assert user.plan == Plan.TRIAL.value


def _create_user(public_id: str, byok: dict | None = None) -> None:
    """Persist a trial user for payment event tests."""
    with sync_session_scope() as session:
        SqlAlchemyUserRepository(session).save(
            UserProfile(
                public_id=public_id,
                email=f"{public_id}@example.com",
                name="Payment User",
                plan=Plan.TRIAL.value,
                plan_label=Plan.TRIAL.limits.label,
                organization_id=None,
                organization_name=None,
                roles=["owner"],
                byok=byok or {},
                usage=default_usage(),
                created_at=123,
                updated_at=123,
            )
        )


def _payment_succeeded_payload(
    *,
    event_id: str,
    user_id: str,
    plan_code: str,
) -> dict:
    """Build a minimal payment.order.succeeded payload."""
    return {
        "event_id": event_id,
        "event_type": "payment.order.succeeded",
        "occurred_at": "2026-06-13T12:00:00Z",
        "order_id": "11111111-1111-7111-8111-111111111111",
        "order_no": "wx202606041200000000000001",
        "user_id": user_id,
        "plan_code": plan_code,
        "billing_period": "monthly",
        "amount": {"currency": "CNY", "total": 19900},
        "provider": {
            "name": "wechatpay",
            "method": "native",
            "merchant_id": "mch-1",
            "merchant_order_no": "wx202606041200000000000001",
            "transaction_id": "4200000000202606130000000001",
            "trade_state": "SUCCESS",
        },
        "entitlements_version": "account-plans-v2",
    }
