"""Usage quota policy helpers shared by application services."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from icore_agent.domain.account.plans import Plan, Usage
from icore_agent.domain.user import UserProfile


def default_usage() -> dict[str, int]:
    """Return a mutable copy of the default usage counters."""
    return asdict(Usage())


def plan_or_free(value: str) -> Plan:
    """Resolve a persisted plan string, defaulting unknown legacy values to free."""
    try:
        return Plan(value)
    except ValueError:
        return Plan.FREE


def ensure_current_usage(
    user: UserProfile,
) -> tuple[UserProfile, dict[str, Any], bool]:
    """Return current usage counters and whether they need to be persisted."""
    usage = dict(user.usage or default_usage())
    should_save = False
    if should_reset_quota(int(usage.get("quota_period_start", 0) or 0)):
        usage = default_usage()
        usage["quota_period_start"] = quota_period_start()
        should_save = True
    elif not user.usage:
        should_save = True
    if should_save:
        user = user.with_usage(usage, updated_at=current_timestamp())
    return user, usage, should_save


def check_quota(
    user: UserProfile,
    usage: Mapping[str, Any],
    resource: str,
    amount: int = 1,
) -> tuple[bool, str | None]:
    """Return whether the user can consume from one quota bucket."""
    limits = plan_or_free(user.plan).limits
    limit, used = quota_limit_and_usage(limits, usage, resource)
    if limit and used + amount > limit:
        return False, f"{resource} quota exceeded for {user.plan}"
    return True, None


def consume_quota(
    user: UserProfile,
    usage: Mapping[str, Any],
    resource: str,
    amount: int = 1,
) -> UserProfile:
    """Return a user copy with one quota bucket incremented."""
    updated_usage = dict(usage)
    key = usage_key(resource)
    updated_usage[key] = int(updated_usage[key]) + amount
    return user.with_usage(updated_usage, updated_at=current_timestamp())


def quota_limit_and_usage(
    limits: Any,
    usage: Mapping[str, Any],
    resource: str,
) -> tuple[int | None, int]:
    """Return the configured limit and current usage for one resource."""
    key = usage_key(resource)
    if key == "message_count":
        return limits.message_limit, int(usage[key])
    if key == "token_count":
        return limits.token_limit, int(usage[key])
    if key == "image_count":
        return limits.image_limit, int(usage[key])
    return limits.attachment_limit, int(usage[key])


def usage_key(resource: str) -> str:
    """Map a quota resource name to its usage counter key."""
    if resource == "messages":
        return "message_count"
    if resource == "tokens":
        return "token_count"
    if resource == "images":
        return "image_count"
    return "attachment_count"


def should_reset_quota(quota_period_start: int) -> bool:
    """Return whether monthly quota counters should reset."""
    if quota_period_start == 0:
        return True
    period_start = datetime.fromtimestamp(quota_period_start, tz=UTC)
    now = datetime.now(UTC)
    if now.year > period_start.year:
        return True
    return now.year == period_start.year and now.month > period_start.month


def quota_period_start() -> int:
    """Return the Unix timestamp for the current quota period start."""
    now = datetime.now(UTC)
    period_start = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=UTC)
    return int(period_start.timestamp())


def next_quota_reset() -> int:
    """Return the Unix timestamp for the next monthly quota reset."""
    now = datetime.now(UTC)
    if now.month == 12:
        reset = datetime(now.year + 1, 1, 1, 0, 0, 0, tzinfo=UTC)
    else:
        reset = datetime(now.year, now.month + 1, 1, 0, 0, 0, tzinfo=UTC)
    return int(reset.timestamp())


def current_timestamp() -> int:
    """Return the current Unix timestamp."""
    return int(datetime.now(UTC).timestamp())
