"""Deterministic criterion aggregation.

PROVEN / NOT_PROVEN / REFUTED  ->  SUPPORTED / MISSING / CONTRADICTED

Rules:
- CONTRADICTED if any sub-requirement is REFUTED (highest precedence)
- MISSING if at least one is NOT_PROVEN and none is REFUTED
- SUPPORTED if every sub-requirement is PROVEN
"""

from __future__ import annotations

from typing import Sequence

from src.atomic_verification.models import AtomicVerifierOutput
from src.common.exceptions import AggregationError
from src.criterion_aggregation.models import CriterionAggregationResult
from src.enums import AtomicLabel, CriterionLabel


def aggregate_criterion(
    criterion_id: str,
    criterion_text: str,
    sub_results: Sequence[AtomicVerifierOutput],
) -> CriterionAggregationResult:
    if not sub_results:
        raise AggregationError(
            f"Criterion {criterion_id} has no sub-requirement results to aggregate"
        )

    labels = [item.output_label for item in sub_results]
    if any(label is AtomicLabel.REFUTED for label in labels):
        label = CriterionLabel.CONTRADICTED
        rationale = (
            f"Criterion {criterion_id} is CONTRADICTED because at least one "
            "sub-requirement is REFUTED. Affirmative conflicting evidence takes "
            "precedence over missing evidence."
        )
    elif any(label is AtomicLabel.NOT_PROVEN for label in labels):
        label = CriterionLabel.MISSING
        rationale = (
            f"Criterion {criterion_id} is MISSING because at least one "
            "sub-requirement is NOT_PROVEN and none is REFUTED. The submitted "
            "documentation does not establish the entire criterion."
        )
    elif all(item is AtomicLabel.PROVEN for item in labels):
        label = CriterionLabel.SUPPORTED
        rationale = (
            f"Criterion {criterion_id} is SUPPORTED because every "
            "sub-requirement is PROVEN."
        )
    else:
        raise AggregationError(
            f"Criterion {criterion_id} has unrecognized atomic labels: {labels!r}"
        )

    return CriterionAggregationResult(
        criterion_id=criterion_id,
        criterion_text=criterion_text,
        label=label,
        sub_requirements=tuple(sub_results),
        rationale=rationale,
    )
