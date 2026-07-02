"""Account billing schemas."""

from pydantic import BaseModel


class ByokRequest(BaseModel):
    """Request body for updating user-owned model gateway settings."""

    api_key: str = ""
    api_base: str = ""
    model: str = ""


class SimulatedPaymentSuccessRequest(BaseModel):
    """Development-only request body for simulating a paid order event."""

    plan_code: str
    billing_period: str = "monthly"
    order_no: str
