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
    assert Plan.FREE.limits.message_limit is None
    # FREE plan: 10_000 tokens/month — enough for 6-10 conversations, nudges upgrade.
    assert Plan.FREE.limits.token_limit == 10_000
    # TRIAL plan: 50_000 tokens one-time gift on registration (~30-50 conversations).
    assert Plan.TRIAL.limits.token_limit == 50_000
    assert Plan.TRIAL.limits.image_limit == 5
    assert Plan.TRIAL.limits.attachment_limit == 10
    # BYOK users supply their own key — no platform token limit.
    assert Plan.BYOK.limits.token_limit is None
