"""Deterministic case-level aggregation.

This decision is explicit business logic and must not be delegated to an LLM.

Rules, in order:
1. Any CONTRADICTED criterion -> NEEDS_CLINICAL_REVIEW
2. Else any MISSING criterion -> DOCUMENTATION_INCOMPLETE
3. Else all SUPPORTED -> READY_FOR_SUBMISSION
"""

from __future__ import annotations

from typing import Sequence

from src.case_aggregation.models import CaseAggregationResult
from src.common.exceptions import AggregationError
from src.criterion_aggregation.models import CriterionAggregationResult
from src.enums import CaseStatus, CriterionLabel


def aggregate_case(
    criterion_results: Sequence[CriterionAggregationResult],
) -> CaseAggregationResult:
    if not criterion_results:
        raise AggregationError("Cannot aggregate a case with no criterion results")

    missing_ids = tuple(
        item.criterion_id
        for item in criterion_results
        if item.label is CriterionLabel.MISSING
    )
    contradicted_ids = tuple(
        item.criterion_id
        for item in criterion_results
        if item.label is CriterionLabel.CONTRADICTED
    )

    if contradicted_ids:
        status = CaseStatus.NEEDS_CLINICAL_REVIEW
        rationale = (
            "Overall status is NEEDS_CLINICAL_REVIEW because at least one "
            f"criterion is CONTRADICTED ({', '.join(contradicted_ids)}). "
            "Contradiction has highest priority, including when other criteria "
            "are also MISSING."
        )
    elif missing_ids:
        status = CaseStatus.DOCUMENTATION_INCOMPLETE
        rationale = (
            "Overall status is DOCUMENTATION_INCOMPLETE because no criterion is "
            "CONTRADICTED and at least one is MISSING "
            f"({', '.join(missing_ids)}). The submitted documentation does not "
            "contain enough evidence to establish every applicable criterion. "
            "This does not assume that the missing evidence exists elsewhere."
        )
    else:
        unsupported = [
            item.criterion_id
            for item in criterion_results
            if item.label is not CriterionLabel.SUPPORTED
        ]
        if unsupported:
            raise AggregationError(
                f"Unrecognized criterion labels for: {unsupported!r}"
            )
        status = CaseStatus.READY_FOR_SUBMISSION
        rationale = (
            "Overall status is READY_FOR_SUBMISSION because every applicable "
            "criterion is SUPPORTED. This means the submitted evidence appears "
            "complete relative to the evaluated policy criteria, not that "
            "coverage or treatment is approved."
        )

    return CaseAggregationResult(
        overall_status=status,
        criterion_results=tuple(criterion_results),
        missing_criterion_ids=missing_ids,
        contradicted_criterion_ids=contradicted_ids,
        rationale=rationale,
    )
