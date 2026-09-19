"""Case-level aggregation result."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from src.criterion_aggregation.models import CriterionAggregationResult
from src.enums import CaseStatus


@dataclass(frozen=True)
class CaseAggregationResult:
    overall_status: CaseStatus
    criterion_results: Tuple[CriterionAggregationResult, ...]
    missing_criterion_ids: Tuple[str, ...]
    contradicted_criterion_ids: Tuple[str, ...]
    rationale: str
