"""
Payment & Billing API

预留 Stripe 集成接口，当前返回 Mock 数据，等公司实体注册后接入真实支付。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...config import settings
from ...control_plane.context import current_user_claims
from ...control_plane.store import ControlPlaneStore

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
    claims: dict = Depends(current_user_claims),
):
    """
    创建 Stripe Checkout Session（当前 Mock）

    TODO: 接入真实 Stripe SDK
    - stripe.checkout.Session.create()
    - 配置 success_url / cancel_url
    - 设置 metadata: user_id, plan, billing_period
    """
    user_id = claims["user_id"]
    
    # Mock: 返回模拟的 checkout URL
    mock_session_id = f"cs_mock_{user_id[:8]}"
    mock_url = f"{settings.icore_base_url or 'http://localhost:8080'}/payment/mock-checkout?session={mock_session_id}"
    
    return CheckoutSessionResponse(
        checkout_url=mock_url,
        session_id=mock_session_id,
    )


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
    claims: dict = Depends(current_user_claims),
):
    """
    手动升级套餐（适用于 BYOK 或线下付款场景）

    不经过 Stripe，直接更新用户套餐。
    """
    user_id = claims["user_id"]
    store = ControlPlaneStore(settings.control_plane_store_path)
    
    if req.plan not in ("team", "enterprise", "byok"):
        raise HTTPException(400, "Invalid plan")
    
    # 如果是 BYOK，必须提供 key
    if req.plan == "byok" and not req.byok_api_key:
        raise HTTPException(400, "BYOK plan requires API key")
    
    user = store.update_user_plan(
        user_id=user_id,
        new_plan=req.plan,
        byok_enabled=(req.plan == "byok"),
        byok_api_key=req.byok_api_key or "",
        byok_api_base=req.byok_api_base or "",
        byok_model=req.byok_model or "",
    )
    
    return {
        "success": True,
        "plan": user["plan"],
        "plan_label": user["plan_label"],
    }


@router.get("/orders", response_model=list[OrderResponse])
async def get_user_orders(
    claims: dict = Depends(current_user_claims),
):
    """
    获取用户的订单列表

    TODO: 从 Control Plane 或数据库读取真实订单记录
    """
    # Mock: 返回空列表
    return []
