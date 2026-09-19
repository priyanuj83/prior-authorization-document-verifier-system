"""Criterion aggregator: deterministic sub-requirement rollup."""

from src.criterion_aggregation.aggregator import aggregate_criterion
from src.criterion_aggregation.models import CriterionAggregationResult

__all__ = [
    "CriterionAggregationResult",
    "aggregate_criterion",
]
