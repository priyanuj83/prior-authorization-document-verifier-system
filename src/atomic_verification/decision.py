"""Label an atomic sub-requirement from extracted facts and derived calculations.

Retrieval scores are not an input. A relevant passage is not proof.
"""

from __future__ import annotations

from typing import Tuple

from src.clinical_extraction.event_models.events import ClinicalEvent, StructuredClinicalFacts
from src.enums import AtomicLabel, EvidenceState
from src.reasoning.temporal_reasoning.models import DerivedFacts


def label_from_structured_evidence(
    facts: StructuredClinicalFacts,
    derived: DerivedFacts,
) -> Tuple[AtomicLabel, str]:
    conflicts = _explicit_conflicts(facts)
    if conflicts:
        return (
            AtomicLabel.REFUTED,
            "An extracted fact explicitly conflicts with the sub-requirement, so the label is REFUTED.",
        )
    explicit_events = _explicit_events(facts)
    if derived.threshold_met is True and explicit_events and derived.continuity_met is not False:
        return (
            AtomicLabel.PROVEN,
            "Deterministic threshold comparison on explicit dates met the policy rule, so the label is PROVEN. "
            + derived.rationale,
        )
    return (
        AtomicLabel.NOT_PROVEN,
        "The submitted evidence does not explicitly establish the sub-requirement. "
        "Retrieved relevance is not proof, and absence of a fact is not proof that the event did not happen. "
        + derived.rationale,
    )


def evidence_events_for_label(
    facts: StructuredClinicalFacts,
    label: AtomicLabel,
) -> Tuple[ClinicalEvent, ...]:
    if label is AtomicLabel.REFUTED:
        return _explicit_conflicts(facts)
    if label is AtomicLabel.PROVEN:
        return _explicit_events(facts)
    return ()


def _explicit_conflicts(facts: StructuredClinicalFacts) -> Tuple[ClinicalEvent, ...]:
    return tuple(
        event
        for event in facts.events
        if event.conflicts_with_requirement and event.evidence_state is EvidenceState.EXPLICIT
    )


def _explicit_events(facts: StructuredClinicalFacts) -> Tuple[ClinicalEvent, ...]:
    return tuple(
        event
        for event in facts.events
        if event.evidence_state is EvidenceState.EXPLICIT and not event.conflicts_with_requirement
    )
