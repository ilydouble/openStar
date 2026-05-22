"""Tests for the deterministic number comparison Strands tool."""

from __future__ import annotations

import json

from icore_agent.application.chat.tools.number_comparator import number_comparator


def test_number_comparator_reports_less_than() -> None:
    """The comparator should report when the left number is smaller."""
    payload = json.loads(number_comparator(left=1, right=2))

    assert payload == {
        "left": 1.0,
        "right": 2.0,
        "comparison": "less_than",
        "difference": -1.0,
        "tolerance": 0.0,
    }


def test_number_comparator_reports_greater_than() -> None:
    """The comparator should report when the left number is larger."""
    payload = json.loads(number_comparator(left=2, right=1))

    assert payload["comparison"] == "greater_than"
    assert payload["difference"] == 1.0


def test_number_comparator_honors_absolute_tolerance() -> None:
    """The comparator should treat nearby values as equal within tolerance."""
    payload = json.loads(number_comparator(
        left=1.0001, right=1.0002, tolerance=0.001))

    assert payload["comparison"] == "equal"
    assert payload["tolerance"] == 0.001
