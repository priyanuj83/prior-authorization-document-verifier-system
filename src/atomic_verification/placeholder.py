"""Placeholder atomic verifier.

Evidence retrieval and model strategy are still open design topics.
This implementation returns a structured NOT_PROVEN result so the
pipeline can run without inventing clinical judgments.
"""

from __future__ import annotations

from typing import Sequence

from src.atomic_verification.decision import (
    evidence_events_for_label,
    label_from_structured_evidence,
)
from src.atomic_verification.models import AtomicVerifierOutput, NoteEvidence
from src.case_loading.models import ClinicalNote, PriorAuthorizationRequest
from src.clinical_extraction.event_models.events import StructuredClinicalFacts
from src.enums import AtomicLabel
from src.reasoning.temporal_reasoning.models import DerivedFacts
from src.requirement_models.models import AtomicSubRequirement
from src.retrieval.query_models.models import CandidateEvidenceSet

PLACEHOLDER_RATIONALE = (
    "Atomic verification is not implemented. Retrieval strategy and model "
    "selection are still open, so this placeholder does not treat absence of "
    "an automated finding as proof that the event did not happen. "
    "The submitted record is therefore labeled NOT_PROVEN for this "
    "sub-requirement."
)


class PlaceholderAtomicVerifier:
    def verify(
        self,
        sub_requirement: AtomicSubRequirement,
        notes: Sequence[ClinicalNote],
        pa_request: PriorAuthorizationRequest,
    ) -> AtomicVerifierOutput:
        del notes, pa_request
        return AtomicVerifierOutput(
            criterion_id=sub_requirement.criterion_id,
            sub_requirement_id=sub_requirement.sub_requirement_id,
            sub_requirement=sub_requirement.text,
            output_label=AtomicLabel.NOT_PROVEN,
            rationale=PLACEHOLDER_RATIONALE,
            notes=(),
        )

    def verify_from_evidence(
        self,
        sub_requirement: AtomicSubRequirement,
        facts: StructuredClinicalFacts,
        derived: DerivedFacts,
        evidence: CandidateEvidenceSet,
    ) -> AtomicVerifierOutput:
        label, rationale = label_from_structured_evidence(facts, derived)
        cited = evidence_events_for_label(facts, label)
        if cited:
            notes = tuple(
                NoteEvidence(
                    file=event.source_file,
                    evidence=event.evidence,
                    evidence_rationale=event.extraction_rationale,
                )
                for event in cited
            )
        elif label is AtomicLabel.NOT_PROVEN:
            notes = tuple(
                NoteEvidence(
                    file=candidate.source_file,
                    evidence=candidate.text,
                    evidence_rationale=(
                        "Retrieved as a candidate from section "
                        f"{candidate.section}. Relevance is not proof, and extraction "
                        "did not establish the sub-requirement."
                    ),
                )
                for candidate in evidence.merged_candidates
            )
        else:
            notes = ()
        return AtomicVerifierOutput(
            criterion_id=sub_requirement.criterion_id,
            sub_requirement_id=sub_requirement.sub_requirement_id,
            sub_requirement=sub_requirement.text,
            output_label=label,
            rationale=rationale,
            notes=notes,
        )
