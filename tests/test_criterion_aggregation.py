from src.common.exceptions import AggregationError
from src.criterion_aggregation import aggregate_criterion
from src.enums import AtomicLabel, CriterionLabel
from tests.helpers import atomic
import pytest


def test_all_proven_is_supported() -> None:
    result = aggregate_criterion(
        "C4",
        "At least 6 weeks of supervised physical therapy.",
        [
            atomic("C4", "1", AtomicLabel.PROVEN),
            atomic("C4", "2", AtomicLabel.PROVEN),
            atomic("C4", "3", AtomicLabel.PROVEN),
            atomic("C4", "4", AtomicLabel.PROVEN),
        ],
    )
    assert result.label is CriterionLabel.SUPPORTED
    assert result.criterion_id == "C4"
    assert len(result.sub_requirements) == 4


def test_not_proven_without_refute_is_missing() -> None:
    result = aggregate_criterion(
        "C4",
        "PT duration",
        [
            atomic("C4", "1", AtomicLabel.PROVEN),
            atomic("C4", "2", AtomicLabel.NOT_PROVEN),
            atomic("C4", "3", AtomicLabel.PROVEN),
        ],
    )
    assert result.label is CriterionLabel.MISSING


def test_any_refuted_is_contradicted_even_if_others_are_missing() -> None:
    """Architecture section 12: CONTRADICTED has higher precedence than MISSING."""

    result = aggregate_criterion(
        "C4",
        "PT duration",
        [
            atomic("C4", "1", AtomicLabel.PROVEN),
            atomic("C4", "2", AtomicLabel.NOT_PROVEN),
            atomic("C4", "3", AtomicLabel.REFUTED, evidence="Patient declined physical therapy."),
            atomic("C4", "4", AtomicLabel.PROVEN),
        ],
    )
    assert result.label is CriterionLabel.CONTRADICTED
    assert result.sub_requirements[2].notes[0].evidence == (
        "Patient declined physical therapy."
    )


def test_empty_sub_requirements_raise() -> None:
    with pytest.raises(AggregationError):
        aggregate_criterion("C1", "text", [])
