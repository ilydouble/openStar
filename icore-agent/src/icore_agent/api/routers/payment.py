"""
Payment & Billing API

预留 Stripe 集成接口，当前返回 Mock 数据，等公司实体注册后接入真实支付。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...application.billing import BillingService
from ..dependencies import get_billing_service, get_current_user

router = APIRouter(prefix="/payment", tags=["payment"])


# ── Request Models ──────────────────────────────────────


class CreateCheckoutSessionRequest(BaseModel):
    plan: str  # "team" | "enterprise"
    billing_period: str = "monthly"  # "monthly" | "annual"


class UpgradePlanRequest(BaseModel):
    plan: str  # "team" | "enterprise" | "byok"
    # 如果是 BYOK，需要提供 key 信息
    byok_api_key: str | None = None
    byok_api_base: str | None = None
    byok_model: str | None = None


# ── Response Models ──────────────────────────────────────


class CheckoutSessionResponse(BaseModel):
    checkout_url: str
    session_id: str


class OrderResponse(BaseModel):
    id: str
    user_id: str
    plan: str
    amount: float
    currency: str
    status: str  # "pending" | "paid" | "failed" | "refunded"
    created_at: int


# ── Endpoints ──────────────────────────────────────────


@router.post("/create-checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    req: CreateCheckoutSessionRequest,
    user: dict = Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
):
    """
    创建 Stripe Checkout Session（当前 Mock）

    TODO: 接入真实 Stripe SDK
    - stripe.checkout.Session.create()
    - 配置 success_url / cancel_url
    - 设置 metadata: user_id, plan, billing_period
    """
    return CheckoutSessionResponse(**service.create_checkout_session(
        user_id=user["id"],
        plan=req.plan,
        billing_period=req.billing_period,
    ))


@router.post("/webhook/stripe")
async def stripe_webhook(
    # TODO: 添加 Stripe 签名验证
    # signature: str = Header(..., alias="stripe-signature"),
):
    """
    Stripe Webhook 回调接口

    TODO: 接入真实 Stripe Webhook 验证
    - 验证 stripe-signature header
    - 处理事件: checkout.session.completed, payment_intent.succeeded, etc.
    - 更新用户套餐和订单状态
    """
    # Mock: 当前不处理任何逻辑
    return {"received": True}


@router.post("/upgrade-plan")
async def upgrade_plan(
    req: UpgradePlanRequest,
    user: dict = Depends(get_current_user),
    service: BillingService = Depends(get_billing_service),
):
    """
    手动升级套餐（适用于 BYOK 或线下付款场景）

    不经过 Stripe，直接更新用户套餐。
    """
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


@router.get("/orders", response_model=list[OrderResponse])
async def get_user_orders(
    user: dict = Depends(get_current_user),
):
    """
    获取用户的订单列表

    TODO: 从 Control Plane 或数据库读取真实订单记录
    """
    # Mock: 返回空列表
    return []
