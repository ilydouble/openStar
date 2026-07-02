"""Account plan and BYOK handlers."""

from uuid import NAMESPACE_URL, uuid5

from fastapi import Depends, HTTPException

from icore_agent.application.account import AccountService
from icore_agent.config import settings
from icore_agent.domain.user import AuthenticatedUser
from icore_agent.infrastructure.control_plane.json_store import control_plane_store
from icore_agent.infrastructure.persistence.payment_events import (
    PostgresPaymentEventRepository,
)

from ...dependencies import get_account_service, get_current_user
from ...users.serializers import serialize_byok
from ..schemas.billing import ByokRequest, SimulatedPaymentSuccessRequest


async def get_plan(
    user: AuthenticatedUser = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
) -> dict:
    """Return the current user's account plan."""
    plan = service.get_plan(user.public_id)
    plan["byok"] = serialize_byok(plan.get("byok"))
    return plan


async def update_byok(
    req: ByokRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    service: AccountService = Depends(get_account_service),
) -> dict:
    """Update Bring Your Own Key settings for the current user."""
    result = service.update_byok(
        user.public_id, req.api_key, req.api_base, req.model)
    return serialize_byok(result)


async def simulate_payment_success(
    req: SimulatedPaymentSuccessRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Apply a development-only simulated payment success event."""
    if not settings.debug:
        raise HTTPException(status_code=404, detail="Not found")

    order_no = req.order_no.strip()
    if not order_no:
        raise HTTPException(status_code=400, detail="order_no is required")

    event_id = f"dev-simulated-payment:{order_no}"
    order_id = str(uuid5(NAMESPACE_URL, event_id))
    repository = PostgresPaymentEventRepository(control_plane_store)
    result = repository.apply_payment_succeeded(
        {
            "event_type": "payment.order.succeeded",
            "event_id": event_id,
            "user_id": user.public_id,
            "plan_code": req.plan_code,
            "billing_period": req.billing_period,
            "order_id": order_id,
            "order_no": order_no,
        }
    )
    if result.status in {"rejected", "deferred"}:
        raise HTTPException(status_code=400, detail=result.reason)
    return {
        "status": result.status,
        "reason": result.reason,
        "order_no": order_no,
        "plan_code": req.plan_code,
    }
