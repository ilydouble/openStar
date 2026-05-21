"""Checkout handlers."""

from fastapi import Depends

from icore_agent.application.billing import BillingService

from ...dependencies import get_billing_service, get_current_user
from ..schemas.checkout import CheckoutSessionResponse, CreateCheckoutSessionRequest


async def create_checkout_session(
    req: CreateCheckoutSessionRequest,
    user: dict = Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
) -> CheckoutSessionResponse:
    """Create a Stripe Checkout session for the selected plan."""
    return CheckoutSessionResponse(**service.create_checkout_session(
        user_id=user["id"],
        plan=req.plan,
        billing_period=req.billing_period,
    ))
