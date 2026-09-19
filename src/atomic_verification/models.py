"""Atomic verifier output contract.

The schema is the same for PROVEN, NOT_PROVEN, and REFUTED.
`notes` is a list because a sub-requirement may depend on multiple documents.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from src.enums import AtomicLabel


@dataclass(frozen=True)
class NoteEvidence:
    """Exact passage from a submitted clinical note, plus why it matters."""

    file: str
    evidence: str
    evidence_rationale: str


@dataclass(frozen=True)
class AtomicVerifierOutput:
    criterion_id: str
    sub_requirement_id: str
    sub_requirement: str
    output_label: AtomicLabel
    rationale: str
    notes: Tuple[NoteEvidence, ...] = ()
