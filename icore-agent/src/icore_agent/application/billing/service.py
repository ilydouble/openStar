"""Application service for billing and checkout flows."""

from __future__ import annotations

from typing import Any, Protocol


class BillingStore(Protocol):
    """Persistence contract used by billing workflows."""

    def update_user_plan(
        self,
        *,
        user_id: str,
        new_plan: str,
        byok_enabled: bool,
        byok_api_key: str,
        byok_api_base: str,
        byok_model: str,
    ) -> dict[str, Any]: ...


class BillingService:
    """Handle billing orchestration without exposing storage details to routers."""

    def __init__(self, store: BillingStore, base_url: str) -> None:
        """Create a billing service with its store adapter and public base URL."""
        self._store = store
        self._base_url = base_url.rstrip("/")

    def create_checkout_session(self, *, user_id: str, plan: str, billing_period: str) -> dict[str, str]:
        """Create a mock checkout session response used by the current product milestone."""
        del plan, billing_period
        session_id = f"cs_mock_{user_id[:8]}"
        return {
            "checkout_url": f"{self._base_url}/payment/mock-checkout?session={session_id}",
            "session_id": session_id,
        }

    def upgrade_plan(
        self,
        *,
        user_id: str,
        plan: str,
        byok_api_key: str | None = None,
        byok_api_base: str | None = None,
        byok_model: str | None = None,
    ) -> dict[str, Any]:
        """Apply the requested billing plan and optional BYOK credentials."""
        if plan not in ("team", "enterprise", "byok"):
            raise ValueError("Invalid plan")
        if plan == "byok" and not byok_api_key:
            raise ValueError("BYOK plan requires API key")
        user = self._store.update_user_plan(
            user_id=user_id,
            new_plan=plan,
            byok_enabled=(plan == "byok"),
            byok_api_key=byok_api_key or "",
            byok_api_base=byok_api_base or "",
            byok_model=byok_model or "",
        )
        return {
            "success": True,
            "plan": user["plan"],
            "plan_label": user["plan_label"],
        }
