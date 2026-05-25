"""Checkout handlers."""

from fastapi import Depends

from icore_agent.application.billing import BillingService
from icore_agent.domain.user import AuthenticatedUser

from ...dependencies import get_billing_service, get_current_user
from ..schemas.checkout import CheckoutSessionResponse, CreateCheckoutSessionRequest


async def create_checkout_session(
    req: CreateCheckoutSessionRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
) -> CheckoutSessionResponse:
    """Create a Stripe Checkout session for the selected plan."""
    return CheckoutSessionResponse(**service.create_checkout_session(
        user_id=user.public_id,
        plan=req.plan,
        billing_period=req.billing_period,
    ))
