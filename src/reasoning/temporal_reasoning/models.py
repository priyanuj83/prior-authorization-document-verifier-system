"""Facts derived by deterministic temporal code."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class DerivedFacts:
    elapsed_days: Optional[int]
    gap_days: Tuple[int, ...]
    continuous_duration_days: Optional[int]
    continuity_met: Optional[bool]
    threshold_met: Optional[bool]
    threshold_days: Optional[int]
    rationale: str
