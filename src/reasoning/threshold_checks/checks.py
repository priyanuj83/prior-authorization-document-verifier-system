"""Threshold comparisons. The comparator comes from the policy, not a guess."""

from __future__ import annotations

from typing import Optional


def compare_threshold(value: int, threshold: int, comparator: Optional[str]) -> bool:
    operator = comparator or ">="
    if operator == ">=":
        return value >= threshold
    if operator == ">":
        return value > threshold
    if operator == "<=":
        return value <= threshold
    if operator == "<":
        return value < threshold
    if operator == "==":
        return value == threshold
    raise ValueError(f"Unsupported threshold comparator: {operator}")
