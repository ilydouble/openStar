from __future__ import annotations

import os
from dataclasses import asdict

import icore_agent.domain.account.plans as constants
from icore_agent.domain.account.plans import Plan, PlanLimits, Usage

os.environ["DEBUG"] = "false"


def test_control_plane_constants_only_expose_dataclass_api():
    """Verify control-plane constants are addressed through typed data objects."""
    assert not hasattr(constants, "DEFAULT_USAGE")
    assert not hasattr(constants, "PLAN_LIMITS")
    # Usage v2: task_count is the primary quota; token_count is for cost tracking.
    assert asdict(Usage()) == {
        "task_count": 0,
        "token_count": 0,
        "quota_period_start": 0,
    }


def test_plan_limits_are_available_as_enum_attributes():
    """Verify plan limits can be referenced without dictionary key lookups."""
    assert not hasattr(Plan, "FREE"), "Plan.FREE must not exist"
    assert not hasattr(Plan, "ENTERPRISE"), "Plan.ENTERPRISE must not exist"

    # TRIAL: free forever, 10 tasks/month.
    assert Plan.TRIAL.value == "trial"
    assert isinstance(Plan.TRIAL.limits, PlanLimits)
    assert Plan.TRIAL.limits.task_limit == 10
    assert Plan.TRIAL.limits.price_usd == 0

    # PRO: $29/month, 200 tasks.
    assert Plan.PRO.value == "pro"
    assert Plan.PRO.limits.task_limit == 200
    assert Plan.PRO.limits.price_usd == 29

    # TEAM: $99/month, 1 000 tasks.
    assert Plan.TEAM.value == "team"
    assert Plan.TEAM.limits.task_limit == 1_000
    assert Plan.TEAM.limits.price_usd == 99

    # PREMIUM: $299/month, 5 000 tasks.
    assert Plan.PREMIUM.value == "premium"
    assert Plan.PREMIUM.limits.task_limit == 5_000
    assert Plan.PREMIUM.limits.price_usd == 299

    # BYOK: unlimited tasks, small infrastructure fee.
    assert Plan.BYOK.value == "byok"
    assert Plan.BYOK.limits.task_limit is None
    assert Plan.BYOK.limits.price_usd == 9
