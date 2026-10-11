"""Deterministic temporal reasoning.

Uses explicit event dates and explicitly stated gap lengths. Does not
invent a continuity threshold when the policy does not provide one.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional, Sequence, Tuple

from src.clinical_extraction.event_models.events import ClinicalEvent, StructuredClinicalFacts
from src.enums import EvidenceState
from src.reasoning.continuity_rules.rules import ContinuityRule, continuity_rule_from_semantics
from src.reasoning.temporal_reasoning.models import DerivedFacts
from src.reasoning.threshold_checks.checks import compare_threshold
from src.requirement_models.semantics import PolicySemantics


class TemporalReasoner:
    def derive(
        self,
        facts: StructuredClinicalFacts,
        semantics: PolicySemantics,
    ) -> DerivedFacts:
        events = [event for event in facts.events if event.evidence_state is EvidenceState.EXPLICIT]
        dated = sorted(
            (event for event in events if event.event_date is not None),
            key=lambda event: event.event_date,
        )
        elapsed = _elapsed_days(dated)
        gaps = _gaps(dated, events)
        rule = continuity_rule_from_semantics(semantics)
        continuity_met, continuous_duration = _continuity(dated, gaps, rule)
        threshold_met, threshold_rationale = _threshold(
            semantics,
            elapsed_days=elapsed,
            continuous_duration_days=continuous_duration,
            continuity_met=continuity_met,
        )
        rationale = " ".join(
            part
            for part in (
                _elapsed_rationale(elapsed, dated),
                _continuity_rationale(rule, continuity_met, continuous_duration),
                threshold_rationale,
            )
            if part
        )
        return DerivedFacts(
            elapsed_days=elapsed,
            gap_days=tuple(gaps),
            continuous_duration_days=continuous_duration,
            continuity_met=continuity_met,
            threshold_met=threshold_met,
            threshold_days=semantics.threshold_days,
            rationale=rationale,
        )


def _elapsed_days(dated: Sequence[ClinicalEvent]) -> Optional[int]:
    if len(dated) < 2:
        return None
    return (dated[-1].event_date - dated[0].event_date).days


def _gaps(dated: Sequence[ClinicalEvent], events: Sequence[ClinicalEvent]) -> List[int]:
    gaps: List[int] = []
    for earlier, later in zip(dated, dated[1:]):
        gaps.append((later.event_date - earlier.event_date).days)
    for event in events:
        if event.gap_duration_days is not None:
            gaps.append(event.gap_duration_days)
    return gaps


def _continuity(
    dated: Sequence[ClinicalEvent],
    gaps: Sequence[int],
    rule: Optional[ContinuityRule],
) -> Tuple[Optional[bool], Optional[int]]:
    if rule is None:
        return None, None
    if not gaps and len(dated) < 2:
        return None, None
    continuity_met = all(gap <= rule.max_gap_days for gap in gaps)
    continuous_duration = _longest_continuous_span(dated, rule.max_gap_days)
    return continuity_met, continuous_duration


def _longest_continuous_span(dated: Sequence[ClinicalEvent], max_gap_days: int) -> Optional[int]:
    if len(dated) < 2:
        return 0 if dated else None
    best = 0
    span_start: date = dated[0].event_date
    previous: date = dated[0].event_date
    for event in dated[1:]:
        current = event.event_date
        gap = (current - previous).days
        if gap <= max_gap_days:
            best = max(best, (current - span_start).days)
        else:
            span_start = current
        previous = current
    return best


def _threshold(
    semantics: PolicySemantics,
    *,
    elapsed_days: Optional[int],
    continuous_duration_days: Optional[int],
    continuity_met: Optional[bool],
) -> Tuple[Optional[bool], str]:
    if semantics.threshold_days is None:
        return None, ""
    if semantics.continuity_required and continuity_met is None:
        return None, (
            "The threshold was not applied because continuity is required and "
            "no continuity rule was supplied."
        )
    if semantics.continuity_required:
        value = continuous_duration_days
        label = "continuous duration"
    else:
        value = elapsed_days
        label = "elapsed duration"
    if value is None:
        return None, f"The {label} could not be calculated from explicit dates."
    met = compare_threshold(value, semantics.threshold_days, semantics.threshold_comparator)
    comparator = semantics.threshold_comparator or ">="
    return met, (
        f"{label.capitalize()} of {value} days {comparator} "
        f"{semantics.threshold_days} is {met}."
    )


def _elapsed_rationale(elapsed: Optional[int], dated: Sequence[ClinicalEvent]) -> str:
    if elapsed is None:
        return "Elapsed calendar duration was not calculated because fewer than two explicit event dates were present."
    return (
        f"Elapsed calendar duration from {dated[0].event_date.isoformat()} "
        f"to {dated[-1].event_date.isoformat()} is {elapsed} days."
    )


def _continuity_rationale(
    rule: Optional[ContinuityRule],
    continuity_met: Optional[bool],
    continuous_duration: Optional[int],
) -> str:
    if rule is None:
        return (
            "No continuity rule was applied. A gap is reported when explicit, "
            "but it is not treated as an automatic failure."
        )
    duration_text = "unknown" if continuous_duration is None else f"{continuous_duration} days"
    return (
        f"Continuity rule max gap {rule.max_gap_days} days: "
        f"continuity_met={continuity_met}, longest continuous span={duration_text}."
    )
