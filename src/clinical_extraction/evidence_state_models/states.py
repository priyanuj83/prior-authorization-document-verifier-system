"""Evidence-state wrapper for one extracted field."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.enums import EvidenceState


@dataclass(frozen=True)
class FactValue:
    """A field value plus how directly the source text supports it.

    value is null when the note does not safely establish the fact.
    """

    value: Optional[object]
    evidence_state: EvidenceState


def not_mentioned() -> FactValue:
    return FactValue(value=None, evidence_state=EvidenceState.NOT_MENTIONED)


def explicit(value: object) -> FactValue:
    return FactValue(value=value, evidence_state=EvidenceState.EXPLICIT)


def ambiguous() -> FactValue:
    return FactValue(value=None, evidence_state=EvidenceState.AMBIGUOUS)
