"""Deterministic number comparison tool for chat agents."""

from __future__ import annotations

import json

from strands import tool


@tool
def number_comparator(left: float, right: float, tolerance: float = 0.0) -> str:
    """Compare two numeric values and return a structured result.

    Use this tool when the answer depends on deterministic numeric ordering,
    especially for values that are close enough to require a tolerance.

    Args:
        left: The first numeric value to compare.
        right: The second numeric value to compare.
        tolerance: Absolute tolerance for treating the two values as equal.

    Returns:
        A JSON string containing the inputs, comparison result, signed
        difference, and absolute tolerance.
    """
    left_value = float(left)
    right_value = float(right)
    effective_tolerance = abs(float(tolerance))
    difference = left_value - right_value

    if abs(difference) <= effective_tolerance:
        comparison = "equal"
    elif difference < 0:
        comparison = "less_than"
    else:
        comparison = "greater_than"

    return json.dumps(
        {
            "left": left_value,
            "right": right_value,
            "comparison": comparison,
            "difference": difference,
            "tolerance": effective_tolerance,
        },
        ensure_ascii=False,
    )
