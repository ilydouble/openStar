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
    assert asdict(Usage()) == {
        "message_count": 0,
        "token_count": 0,
        "image_count": 0,
        "attachment_count": 0,
        "quota_period_start": 0,
    }


def test_plan_limits_are_available_as_enum_attributes():
    """Verify plan limits can be referenced without dictionary key lookups."""
    assert Plan.FREE.value == "free"
    assert isinstance(Plan.FREE.limits, PlanLimits)
    assert Plan.FREE.limits.message_limit == 5
    assert Plan.FREE.limits.token_limit == 3_000
    assert Plan.BYOK.limits.token_limit is None
