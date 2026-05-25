"""Shared control-plane constants for plans and usage counters."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True, slots=True)
class Usage:
    message_count: int = 0
    token_count: int = 0
    image_count: int = 0
    attachment_count: int = 0
    quota_period_start: int = 0


@dataclass(frozen=True, slots=True)
class PlanLimits:
    message_limit: int | None
    token_limit: int | None
    image_limit: int
    attachment_limit: int
    label: str


class Plan(str, Enum):  # noqa: UP042 - keep the existing enum contract unchanged.
    limits: PlanLimits

    # Trial: one-time registration gift (~30-50 real AI conversations).
    # token_limit=50_000 costs us ~¥5-10 per user; generous enough to
    # demonstrate value, small enough to control burn rate.
    # No monthly reset — use it or lose it.
    TRIAL = (
        "trial",
        PlanLimits(
            message_limit=None,
            token_limit=50_000,
            image_limit=5,
            attachment_limit=10,
            label="Trial",
        ),
    )

    # Free: monthly allowance after trial expires.
    # Just enough to remind users the product exists (6-10 conversations/month)
    # and create a clear upgrade nudge without being completely useless.
    FREE = (
        "free",
        PlanLimits(
            message_limit=None,
            token_limit=10_000,
            image_limit=1,
            attachment_limit=2,
            label="Free",
        ),
    )

    # Team: paid tier (~¥99/month), 600-1000 conversations/month.
    TEAM = (
        "team",
        PlanLimits(
            message_limit=None,
            token_limit=1_000_000,
            image_limit=100,
            attachment_limit=200,
            label="Team",
        ),
    )

    # Enterprise: paid tier (~¥999/month), 6000-10000 conversations/month.
    ENTERPRISE = (
        "enterprise",
        PlanLimits(
            message_limit=None,
            token_limit=10_000_000,
            image_limit=1_000,
            attachment_limit=5_000,
            label="Enterprise",
        ),
    )

    # BYOK: user supplies their own API key — platform charges a small
    # infrastructure fee. token_limit=None means no quota enforcement.
    BYOK = (
        "byok",
        PlanLimits(
            message_limit=None,
            token_limit=None,
            image_limit=200,
            attachment_limit=400,
            label="BYOK",
        ),
    )

    def __new__(cls, value: str, limits: PlanLimits):
        """Create a plan enum member with typed usage limits attached."""
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.limits = limits
        return obj
