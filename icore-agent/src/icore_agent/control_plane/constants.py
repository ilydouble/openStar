"""Shared control-plane constants for plans and usage counters."""

from __future__ import annotations

DEFAULT_USAGE: dict[str, int] = {
    "message_count": 0,
    "token_count": 0,
    "image_count": 0,
    "attachment_count": 0,
    "quota_period_start": 0,
}

PLAN_LIMITS: dict[str, dict[str, int | str]] = {
    "trial": {
        "message_limit": 0,
        "token_limit": 0,
        "image_limit": 0,
        "attachment_limit": 0,
        "label": "Trial",
    },
    "free": {
        "message_limit": 5,
        "token_limit": 3_000,
        "image_limit": 1,
        "attachment_limit": 1,
        "label": "Free",
    },
    "team": {
        "message_limit": 800,
        "token_limit": 2_000_000,
        "image_limit": 200,
        "attachment_limit": 400,
        "label": "Team",
    },
    "enterprise": {
        "message_limit": 10_000,
        "token_limit": 20_000_000,
        "image_limit": 2_000,
        "attachment_limit": 10_000,
        "label": "Enterprise",
    },
    "byok": {
        "message_limit": 800,
        "token_limit": 0,
        "image_limit": 200,
        "attachment_limit": 400,
        "label": "BYOK",
    },
}
