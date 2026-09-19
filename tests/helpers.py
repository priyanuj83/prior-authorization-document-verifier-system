"""Atomic helper used by aggregator tests."""

from src.atomic_verification.models import AtomicVerifierOutput, NoteEvidence
from src.enums import AtomicLabel


def atomic(
    criterion_id: str,
    suffix: str,
    label: AtomicLabel,
    text: str = "",
    evidence: str = "",
) -> AtomicVerifierOutput:
    notes = ()
    if evidence:
        notes = (
            NoteEvidence(
                file="example-note.md",
                evidence=evidence,
                evidence_rationale="Fixture evidence.",
            ),
        )
    return AtomicVerifierOutput(
        criterion_id=criterion_id,
        sub_requirement_id=f"{criterion_id}.{suffix}",
        sub_requirement=text or f"{criterion_id}.{suffix}",
        output_label=label,
        rationale=f"Fixture label {label.value}",
        notes=notes,
    )
