from src.case_aggregation import aggregate_case
from src.common.exceptions import AggregationError
from src.criterion_aggregation.models import CriterionAggregationResult
from src.enums import CaseStatus, CriterionLabel
import pytest


def _criterion(criterion_id: str, label: CriterionLabel) -> CriterionAggregationResult:
    return CriterionAggregationResult(
        criterion_id=criterion_id,
        criterion_text=criterion_id,
        label=label,
        sub_requirements=(),
        rationale="fixture",
    )


def test_any_contradicted_needs_clinical_review() -> None:
    result = aggregate_case(
        [
            _criterion("C1", CriterionLabel.SUPPORTED),
            _criterion("C2", CriterionLabel.CONTRADICTED),
            _criterion("C3", CriterionLabel.SUPPORTED),
            _criterion("C4", CriterionLabel.MISSING),
        ]
    )
    assert result.overall_status is CaseStatus.NEEDS_CLINICAL_REVIEW
    assert result.contradicted_criterion_ids == ("C2",)
    assert result.missing_criterion_ids == ("C4",)


def test_missing_without_contradiction_is_documentation_incomplete() -> None:
    result = aggregate_case(
        [
            _criterion("C1", CriterionLabel.SUPPORTED),
            _criterion("C2", CriterionLabel.SUPPORTED),
            _criterion("C3", CriterionLabel.MISSING),
            _criterion("C4", CriterionLabel.SUPPORTED),
        ]
    )
    assert result.overall_status is CaseStatus.DOCUMENTATION_INCOMPLETE
    assert result.missing_criterion_ids == ("C3",)
    assert result.contradicted_criterion_ids == ()


def test_all_supported_is_ready_for_submission() -> None:
    result = aggregate_case(
        [
            _criterion("C1", CriterionLabel.SUPPORTED),
            _criterion("C2", CriterionLabel.SUPPORTED),
            _criterion("C3", CriterionLabel.SUPPORTED),
            _criterion("C4", CriterionLabel.SUPPORTED),
        ]
    )
    assert result.overall_status is CaseStatus.READY_FOR_SUBMISSION
    assert "coverage" in result.rationale.lower() or "approved" in result.rationale.lower()


def test_empty_criteria_raise() -> None:
    with pytest.raises(AggregationError):
        aggregate_case([])
