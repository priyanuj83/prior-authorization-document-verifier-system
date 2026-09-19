"""Criterion-level aggregation result."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from src.atomic_verification.models import AtomicVerifierOutput
from src.enums import CriterionLabel


@dataclass(frozen=True)
class CriterionAggregationResult:
    criterion_id: str
    criterion_text: str
    label: CriterionLabel
    sub_requirements: Tuple[AtomicVerifierOutput, ...]
    rationale: str
