"""Repository for applying payment integration events to account state."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from icore_agent.application.usage.policy import current_timestamp
from icore_agent.domain.account.plans import Plan

from .payment_event_models import ProcessedPaymentEvent
from .sqlalchemy.sync_session import sync_session_scope
from .users.sqlalchemy_repository import SqlAlchemyUserRepository


class ControlPlaneEventStore(Protocol):
    """Store used to record account-side payment application events."""

    def append_event(self, event_type: str, **payload: Any) -> None:
        """Append one control-plane event."""


@dataclass(frozen=True, slots=True)
class PaymentEventApplyResult:
    """Result of applying or skipping one payment event."""

    status: str
    reason: str = ""


class PostgresPaymentEventRepository:
    """Apply payment-service success events to PostgreSQL account profiles."""

    def __init__(self, store: ControlPlaneEventStore) -> None:
        """Create a repository with a control-plane event sink."""
        self._store = store

    def apply_payment_succeeded(self, payload: dict[str, Any]) -> PaymentEventApplyResult:
        """Apply one payment.order.succeeded payload idempotently."""
        event_type = _required_string(payload, "event_type")
        if event_type != "payment.order.succeeded":
            return PaymentEventApplyResult("ignored", "unsupported event type")

        event_id = _required_string(payload, "event_id")
        user_id = _required_string(payload, "user_id")
        plan_code = _required_string(payload, "plan_code")
        billing_period = _required_string(payload, "billing_period")
        order_id = _required_string(payload, "order_id")
        order_no = _required_string(payload, "order_no")

        try:
            plan = Plan(plan_code)
        except ValueError:
            return PaymentEventApplyResult("rejected", f"unsupported plan: {plan_code}")

        event_to_append: tuple[str, dict[str, Any]] | None = None
        try:
            with sync_session_scope() as session:
                existing = session.get(ProcessedPaymentEvent, event_id)
                if existing is not None:
                    return PaymentEventApplyResult("duplicate")

                users = SqlAlchemyUserRepository(session)
                user = users.get_by_public_id(user_id)
                if user is None:
                    return PaymentEventApplyResult("rejected", f"user not found: {user_id}")
                if plan == Plan.BYOK and not _byok_credentials_configured(user.byok):
                    return PaymentEventApplyResult("deferred", "byok credentials required")

                old_plan = user.plan
                users.save(
                    replace(
                        user,
                        plan=plan.value,
                        plan_label=plan.limits.label,
                        updated_at=current_timestamp(),
                    )
                )
                session.add(
                    ProcessedPaymentEvent(
                        event_id=event_id,
                        event_type=event_type,
                        order_id=order_id,
                        order_no=order_no,
                        user_public_id=user_id,
                        plan_code=plan.value,
                        billing_period=billing_period,
                        payload=dict(payload),
                    )
                )
                event_to_append = (
                    "payment_plan_applied",
                    {
                        "user_id": user_id,
                        "old_plan": old_plan,
                        "new_plan": plan.value,
                        "event_id": event_id,
                        "order_id": order_id,
                        "order_no": order_no,
                    },
                )
        except IntegrityError:
            return PaymentEventApplyResult("duplicate")

        if event_to_append is not None:
            event_type_name, event_payload = event_to_append
            self._store.append_event(event_type_name, **event_payload)
        return PaymentEventApplyResult("applied")


def _required_string(payload: dict[str, Any], key: str) -> str:
    """Read one required non-empty string from a payment event payload."""
    value = str(payload.get(key) or "").strip()
    if not value:
        raise ValueError(f"payment event missing {key}")
    return value


def _byok_credentials_configured(byok: dict[str, Any]) -> bool:
    """Return whether BYOK has been explicitly enabled with a user API key."""
    return bool(byok.get("enabled")) and bool(str(byok.get("api_key") or "").strip())
