"""Atomic verifier protocol.

Given an already-resolved sub-requirement and clinical evidence, determine
PROVEN / NOT_PROVEN / REFUTED. The verifier does not choose the policy.
"""

from __future__ import annotations

from typing import Protocol, Sequence

from src.atomic_verification.models import AtomicVerifierOutput
from src.case_loading.models import ClinicalNote, PriorAuthorizationRequest
from src.requirement_models.models import AtomicSubRequirement


class AtomicVerifier(Protocol):
    def verify(
        self,
        sub_requirement: AtomicSubRequirement,
        notes: Sequence[ClinicalNote],
        pa_request: PriorAuthorizationRequest,
    ) -> AtomicVerifierOutput:
        """Evaluate one atomic sub-requirement against submitted records."""
