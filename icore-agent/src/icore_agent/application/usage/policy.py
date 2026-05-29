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


def plan_or_trial(value: str) -> Plan:
    """Resolve a persisted plan string, defaulting unknown/legacy values to TRIAL.

    Legacy DB rows that still carry 'free' will be treated as TRIAL so they
    continue to receive quota enforcement without a hard migration.
    """
    try:
        return Plan(value)
    except ValueError:
        return Plan.TRIAL


def ensure_current_usage(
    user: UserProfile,
) -> tuple[UserProfile, dict[str, Any], bool]:
    """Return current usage counters and whether they need to be persisted."""
    usage = {**default_usage(), **dict(user.usage or {})}

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
    """Return whether the user can consume from one quota bucket.

    Only 'tasks' is enforced as a hard quota.  Token counts are tracked
    internally for cost reporting but never block a request.
    """
    limits = plan_or_trial(user.plan).limits
    limit, used = quota_limit_and_usage(limits, usage, resource)
    if limit is not None and used + amount > limit:
        return False, f"{resource} quota exceeded for plan '{user.plan}'"
    return True, None


def estimated_cost_from_tokens(token_count: int) -> float:
    """Return the platform estimated cost for a token total."""
    return round(int(token_count) / 1_000_000 * 2.0, 6)


def append_llm_usage_stats(
    user: UserProfile,
    usage: Mapping[str, Any],
    *,
    model: str,
    total_tokens: int,
    estimated_cost: float,
) -> UserProfile:
    """Return a user copy with per-model LLM call analytics appended."""
    updated_usage = {**default_usage(), **dict(usage)}
    normalized_model = (model or "unknown").strip() or "unknown"
    updated_usage["llm_call_count"] = int(
        updated_usage.get("llm_call_count", 0) or 0) + 1
    models_used = [
        str(item).strip()
        for item in (updated_usage.get("models_used") or [])
        if str(item).strip()
    ]
    if normalized_model not in models_used:
        models_used.append(normalized_model)
    updated_usage["models_used"] = models_used
    by_model = dict(updated_usage.get("by_model") or {})
    entry = dict(
        by_model.get(normalized_model) or {
            "calls": 0, "tokens": 0, "cost": 0.0}
    )
    entry["calls"] = int(entry.get("calls", 0) or 0) + 1
    entry["tokens"] = int(entry.get("tokens", 0) or 0) + int(total_tokens)
    entry["cost"] = round(
        float(entry.get("cost", 0.0) or 0.0) + float(estimated_cost), 6)
    by_model[normalized_model] = entry
    updated_usage["by_model"] = by_model
    return user.with_usage(updated_usage, updated_at=current_timestamp())


def plan_usage_analytics(usage: Mapping[str, Any]) -> dict[str, Any]:
    """Derive billing-plan analytics fields from PostgreSQL usage counters."""
    normalized = {**default_usage(), **dict(usage)}
    token_count = int(normalized.get("token_count", 0) or 0)
    by_model = {
        str(model): {
            "calls": int(stats.get("calls", 0) or 0),
            "tokens": int(stats.get("tokens", 0) or 0),
            "cost": round(float(stats.get("cost", 0.0) or 0.0), 6),
        }
        for model, stats in dict(normalized.get("by_model") or {}).items()
    }
    models_used = [
        str(item).strip()
        for item in (normalized.get("models_used") or [])
        if str(item).strip()
    ]
    model_calls = int(normalized.get("llm_call_count", 0) or 0)
    if model_calls == 0 and by_model:
        model_calls = sum(entry["calls"] for entry in by_model.values())
    if by_model:
        estimated_cost = round(sum(entry["cost"]
                               for entry in by_model.values()), 6)
    else:
        estimated_cost = estimated_cost_from_tokens(token_count)
    active_models = len(models_used) if models_used else len(by_model)
    return {
        "estimated_cost": estimated_cost,
        "model_calls": model_calls,
        "active_models": active_models,
        "by_model": by_model,
        "models_used": models_used or list(by_model.keys()),
    }


def admin_usage_overview(
    users: list[UserProfile],
    *,
    now: int | None = None,
    new_trials_7d: int = 0,
    leads: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate admin usage metrics from PostgreSQL user profiles."""
    timestamp = now or current_timestamp()
    active_window = timestamp - 7 * 24 * 3600
    by_model: dict[str, dict[str, Any]] = {}
    total_tokens = 0
    total_cost = 0.0
    total_calls = 0
    for user in users:
        usage = {**default_usage(), **dict(user.usage or {})}
        analytics = plan_usage_analytics(usage)
        total_tokens += int(usage.get("token_count", 0) or 0)
        total_cost += float(analytics["estimated_cost"])
        total_calls += int(analytics["model_calls"])
        for model, stats in analytics["by_model"].items():
            entry = by_model.setdefault(
                model,
                {"calls": 0, "tokens": 0, "cost": 0.0},
            )
            entry["calls"] += int(stats["calls"])
            entry["tokens"] += int(stats["tokens"])
            entry["cost"] = round(entry["cost"] + float(stats["cost"]), 6)
    for entry in by_model.values():
        entry["cost"] = round(entry["cost"], 6)
    heavy_users = sorted(
        (
            {
                "user_id": user.public_id,
                "email": user.email,
                "tokens": int((user.usage or {}).get("token_count", 0) or 0),
                "messages": int((user.usage or {}).get("message_count", 0) or 0),
                "plan": user.plan,
            }
            for user in users
        ),
        key=lambda item: (item["tokens"], item["messages"]),
        reverse=True,
    )[:5]
    lead_stats = dict(leads or {})
    return {
        "users": {
            "total": len(users),
            "active_7d": sum(
                1 for user in users if int(user.updated_at or 0) >= active_window
            ),
            "trial": sum(
                1 for user in users if user.plan in ("trial", "free")
            ),
            "byok_enabled": sum(
                1 for user in users if (user.byok or {}).get("enabled")
            ),
            "new_trials_7d": int(new_trials_7d),
        },
        "leads": {
            "total": int(lead_stats.get("total", 0) or 0),
            "enterprise": int(lead_stats.get("enterprise", 0) or 0),
            "demo": int(lead_stats.get("demo", 0) or 0),
        },
        "usage": {
            "total_calls": total_calls,
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 6),
            "by_model": by_model,
        },
        "heavy_users": heavy_users,
    }


def consume_quota(
    user: UserProfile,
    usage: Mapping[str, Any],
    resource: str,
    amount: int = 1,
) -> UserProfile:
    """Return a user copy with one quota bucket incremented."""
    updated_usage = {**default_usage(), **dict(usage)}
    key = usage_key(resource)

    updated_usage[key] = int(updated_usage.get(key, 0) or 0) + amount

    return user.with_usage(updated_usage, updated_at=current_timestamp())


def quota_limit_and_usage(
    limits: Any,
    usage: Mapping[str, Any],
    resource: str,
) -> tuple[int | None, int]:
    """Return the configured limit and current usage for one resource."""
    normalized = {**default_usage(), **dict(usage)}
    key = usage_key(resource)
    used = int(normalized.get(key, 0) or 0)

    if resource == "tasks":
        return limits.task_limit, used
    if resource == "attachments":
        return limits.attachment_limit, used
    if resource == "tokens":
        return None, used
    # Legacy v1 resource names fall back to attachment limits when present.
    if key == "message_count":
        return limits.task_limit, used
    if key == "image_count":
        return limits.attachment_limit, used
    return limits.attachment_limit, used


def usage_key(resource: str) -> str:
    """Map a quota resource name to its usage counter key."""
    if resource == "tasks":
        return "task_count"
    if resource == "tokens":
        return "token_count"
    if resource == "attachments":
        return "attachment_count"
    if resource == "messages":
        return "message_count"
    if resource == "images":
        return "image_count"
    return "token_count"


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
