"""Case aggregator: deterministic criterion rollup to overall status."""

from src.case_aggregation.aggregator import aggregate_case
from src.case_aggregation.models import CaseAggregationResult

__all__ = [
    "CaseAggregationResult",
    "aggregate_case",
]
