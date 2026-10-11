"""Compare provider attestations with already verified evidence.

This component must not be used to generate retrieval hints.
"""

from __future__ import annotations

from typing import Protocol, Sequence

from src.attestation_verification.models import AttestationCheck
from src.case_loading.models import Attestation
from src.requirement_models.models import AtomicSubRequirement


class AttestationVerifier(Protocol):
    def check(
        self,
        attestations: Sequence[Attestation],
        verified_requirements: Sequence[AtomicSubRequirement],
    ) -> tuple:
        """Return one check per attestation. Do not search the chart."""
