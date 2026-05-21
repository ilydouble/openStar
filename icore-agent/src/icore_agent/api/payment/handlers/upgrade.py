"""Plan upgrade handlers."""

from fastapi import Depends, HTTPException

from ....application.billing import BillingService
from ...dependencies import get_billing_service, get_current_user
from ..schemas.upgrade import UpgradePlanRequest


async def upgrade_plan(
    req: UpgradePlanRequest,
    user: dict = Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
) -> dict:
    """Upgrade a plan directly for BYOK or offline payment scenarios."""
    try:
        return service.upgrade_plan(
            user_id=user["id"],
            plan=req.plan,
            byok_api_key=req.byok_api_key,
            byok_api_base=req.byok_api_base,
            byok_model=req.byok_model,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
