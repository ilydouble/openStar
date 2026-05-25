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

    TRIAL = (
        "trial",
        PlanLimits(
            message_limit=None,
            token_limit=0,
            image_limit=0,
            attachment_limit=0,
            label="Trial",
        ),
    )

    FREE = (
        "free",
        PlanLimits(
            message_limit=None,
            token_limit=3_000,
            image_limit=1,
            attachment_limit=1,
            label="Free",
        ),
    )

    TEAM = (
        "team",
        PlanLimits(
            message_limit=None,
            token_limit=2_000_000,
            image_limit=200,
            attachment_limit=400,
            label="Team",
        ),
    )

    ENTERPRISE = (
        "enterprise",
        PlanLimits(
            message_limit=None,
            token_limit=20_000_000,
            image_limit=2_000,
            attachment_limit=10_000,
            label="Enterprise",
        ),
    )

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
