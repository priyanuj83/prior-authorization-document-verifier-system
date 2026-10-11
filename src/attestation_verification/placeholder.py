"""Placeholder attestation comparer.

Does not read attestations as clinical truth and does not assign
SUPPORTED, NOT_SUPPORTED, or CONFLICTED until a real comparison exists.
"""

from __future__ import annotations

from typing import Sequence, Tuple

from src.attestation_verification.models import AttestationCheck
from src.case_loading.models import Attestation
from src.requirement_models.models import AtomicSubRequirement

_RATIONALE = (
    "Attestations are excluded from retrieval and are not evaluated by the "
    "placeholder comparer. Policy verification remains a separate result."
)


class PlaceholderAttestationVerifier:
    def check(
        self,
        attestations: Sequence[Attestation],
        verified_requirements: Sequence[AtomicSubRequirement],
    ) -> Tuple[AttestationCheck, ...]:
        del verified_requirements
        return tuple(
            AttestationCheck(
                attestation_id=item.id,
                verdict=None,
                rationale=_RATIONALE,
            )
            for item in attestations
        )
