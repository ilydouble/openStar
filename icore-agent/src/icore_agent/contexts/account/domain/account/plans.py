"""Shared control-plane constants for plans and usage counters.

Quota model (v2): the user-visible unit is a *task* (one complete agent turn).
Token counts are recorded internally for cost tracking but are NOT enforced
as a hard quota.  All plans — including Trial — reset monthly.

Plan ladder:
  Trial   – free forever,  10 tasks/month  (always-on acquisition hook)
  Pro     – $29/month,    200 tasks/month  (individual sellers / creators)
  Team    – $99/month,  1 000 tasks/month  (small teams)
  Premium – $299/month, 5 000 tasks/month  (integrations: Shopify, CRM, …)
  BYOK    – $9/month,   unlimited          (user supplies own API key)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True, slots=True)
class Usage:
    """Per-user usage counters stored as a JSON blob in the DB."""

    # Primary quota counter — one unit consumed per completed agent turn.
    task_count: int = 0
    # Internal cost tracking only; not enforced as a hard quota.
    token_count: int = 0
    # Attachments uploaded within the current quota period.
    attachment_count: int = 0
    # Timestamp of the current quota period start (Unix seconds).
    quota_period_start: int = 0


@dataclass(frozen=True, slots=True)
class PlanLimits:
    """Limits attached to each plan tier."""

    # Maximum tasks per quota period; None = unlimited (BYOK).
    task_limit: int | None
    # Human-readable tier label shown in the UI.
    label: str
    # Monthly price in USD (0 = free).
    price_usd: int = 0
    # Maximum attachments per quota period; None = unlimited (BYOK).
    attachment_limit: int | None = 100


class Plan(str, Enum):  # noqa: UP042 - keep the existing enum contract unchanged.
    limits: PlanLimits

    # Free forever — resets monthly.  Keeps a permanent acquisition hook so
    # churned users can always come back and re-experience the product.
    TRIAL = (
        "trial",
        PlanLimits(task_limit=10, label="Trial",
                   price_usd=0, attachment_limit=10),
    )

    # Individual sellers, freelancers, solo creators.
    PRO = (
        "pro",
        PlanLimits(task_limit=200, label="Pro",
                   price_usd=29, attachment_limit=100),
    )

    # Small teams that collaborate on agent workflows.
    TEAM = (
        "team",
        PlanLimits(task_limit=1_000, label="Team",
                   price_usd=99, attachment_limit=400),
    )

    # Power users who need platform integrations (Shopify, CRM, WhatsApp, …).
    PREMIUM = (
        "premium",
        PlanLimits(task_limit=5_000, label="Premium",
                   price_usd=299, attachment_limit=2000),
    )

    # User supplies their own LLM API key; platform charges infra fee only.
    BYOK = (
        "byok",
        PlanLimits(task_limit=None, label="BYOK",
                   price_usd=9, attachment_limit=None),
    )

    def __new__(cls, value: str, limits: PlanLimits):
        """Create a plan enum member with typed usage limits attached."""
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.limits = limits
        return obj
