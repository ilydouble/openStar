"""Payment API router."""

from fastapi import APIRouter, Depends

from ..dependencies import get_current_user
from .handlers import create_checkout_session, get_user_orders, stripe_webhook, upgrade_plan
from .schemas import CheckoutSessionResponse, OrderResponse

router = APIRouter(
    prefix="/api/v1/payment",
    tags=["payment"],
    dependencies=[Depends(get_current_user)],
)

router.post(
    "/create-checkout-session",
    response_model=CheckoutSessionResponse,
)(create_checkout_session)
router.post("/webhook/stripe")(stripe_webhook)
router.post("/upgrade-plan")(upgrade_plan)
router.get("/orders", response_model=list[OrderResponse])(get_user_orders)
