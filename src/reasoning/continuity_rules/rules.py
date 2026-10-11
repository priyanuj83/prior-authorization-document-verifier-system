"""Continuity limits come from policy language. This module does not invent one."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.requirement_models.semantics import PolicySemantics


@dataclass(frozen=True)
class ContinuityRule:
    max_gap_days: int


def continuity_rule_from_semantics(semantics: PolicySemantics) -> Optional[ContinuityRule]:
    if semantics.continuity_max_gap_days is None:
        return None
    return ContinuityRule(max_gap_days=semantics.continuity_max_gap_days)
