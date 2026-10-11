"""Retrieval-oriented policy semantics persisted with each atomic requirement.

These fields say what to search for and which calculations are allowed.
They are not clinical evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from src.policy_models.models import PolicyCriterion


@dataclass(frozen=True)
class PolicySemantics:
    required_facts: Tuple[str, ...] = ()
    supporting_patterns: Tuple[str, ...] = ()
    refuting_conditions: Tuple[str, ...] = ()
    insufficient_information: Tuple[str, ...] = ()
    calculation_required: bool = False
    calculation_type: Optional[str] = None
    continuity_required: bool = False
    # Set only when the policy states a maximum acceptable gap. Never invented.
    continuity_max_gap_days: Optional[int] = None
    threshold_days: Optional[int] = None
    threshold_comparator: Optional[str] = None
    lookback_days: Optional[int] = None
    # Date windows are search hints unless the policy marks one as a hard filter.
    hard_date_filter: bool = False


def semantics_from_criterion(criterion: PolicyCriterion) -> PolicySemantics:
    """Copy structured fields already present on the authored criterion.

    Does not invent atomic facts, continuity limits, or hard lookbacks.
    """

    metadata = criterion.metadata or {}
    threshold = metadata.get("threshold") if isinstance(metadata.get("threshold"), dict) else {}
    failure_modes = metadata.get("failure_modes") if isinstance(metadata.get("failure_modes"), dict) else {}

    duration = threshold.get("duration_days")
    threshold_days = int(duration) if isinstance(duration, int) else None
    comparator = threshold.get("comparator")
    lookback = metadata.get("lookback_days")
    lookback_days = int(lookback) if isinstance(lookback, int) else None
    max_gap = metadata.get("continuity_max_gap_days")
    continuity_max_gap_days = int(max_gap) if isinstance(max_gap, int) else None

    refuting = _text_list(failure_modes.get("contradicted"))
    insufficient = _text_list(failure_modes.get("missing"))
    supporting = _text_list(metadata.get("supporting_patterns"))
    required = _text_list(metadata.get("required_facts"))

    return PolicySemantics(
        required_facts=tuple(required),
        supporting_patterns=tuple(supporting),
        refuting_conditions=tuple(refuting),
        insufficient_information=tuple(insufficient),
        calculation_required=threshold_days is not None or bool(metadata.get("calculation_required")),
        calculation_type="temporal_duration" if threshold_days is not None else metadata.get("calculation_type"),
        continuity_required=bool(metadata.get("continuity_required", False)),
        continuity_max_gap_days=continuity_max_gap_days,
        threshold_days=threshold_days,
        threshold_comparator=str(comparator) if comparator else None,
        lookback_days=lookback_days,
        hard_date_filter=bool(metadata.get("hard_date_filter", False)),
    )


def _text_list(value) -> Tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        text = " ".join(value.split())
        return (text,) if text else ()
    if isinstance(value, (list, tuple)):
        items = []
        for item in value:
            text = " ".join(str(item).split())
            if text:
                items.append(text)
        return tuple(items)
    text = " ".join(str(value).split())
    return (text,) if text else ()
