"""Order schemas."""

from pydantic import BaseModel


class OrderResponse(BaseModel):
    id: str
    user_id: str
    plan: str
    amount: float
    currency: str
    status: str  # "pending" | "paid" | "failed" | "refunded"
    created_at: int
