"""Placeholder atomic verifier.

Evidence retrieval and model strategy are still open design topics.
This implementation returns a structured NOT_PROVEN result so the
pipeline can run without inventing clinical judgments.
"""

from __future__ import annotations

from typing import Sequence

from src.atomic_verification.models import AtomicVerifierOutput
from src.case_loading.models import ClinicalNote, PriorAuthorizationRequest
from src.enums import AtomicLabel
from src.requirement_models.models import AtomicSubRequirement

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
