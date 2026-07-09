"""Checkout schemas."""

from pydantic import BaseModel


class CreateCheckoutSessionRequest(BaseModel):
    plan: str  # "team" | "enterprise"
    billing_period: str = "monthly"  # "monthly" | "annual"


class CheckoutSessionResponse(BaseModel):
    checkout_url: str
    session_id: str
