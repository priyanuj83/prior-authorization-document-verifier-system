"""Atomic verifier protocol.

Given an already-resolved sub-requirement and structured evidence, determine
PROVEN / NOT_PROVEN / REFUTED. The verifier does not choose the policy and
does not treat retrieval similarity as proof.

`verify` remains for callers that have not yet produced extracted facts.
`verify_from_evidence` is the retrieval-architecture contract.
"""

from __future__ import annotations

from typing import Protocol, Sequence

from src.atomic_verification.models import AtomicVerifierOutput
from src.case_loading.models import ClinicalNote, PriorAuthorizationRequest
from src.clinical_extraction.event_models.events import StructuredClinicalFacts
from src.reasoning.temporal_reasoning.models import DerivedFacts
from src.requirement_models.models import AtomicSubRequirement
from src.retrieval.query_models.models import CandidateEvidenceSet


class AtomicVerifier(Protocol):
    def verify(
        self,
        sub_requirement: AtomicSubRequirement,
        notes: Sequence[ClinicalNote],
        pa_request: PriorAuthorizationRequest,
    ) -> AtomicVerifierOutput:
        """Evaluate one atomic sub-requirement against submitted records."""


class EvidenceBackedAtomicVerifier(Protocol):
    def verify_from_evidence(
        self,
        sub_requirement: AtomicSubRequirement,
        facts: StructuredClinicalFacts,
        derived: DerivedFacts,
        evidence: CandidateEvidenceSet,
    ) -> AtomicVerifierOutput:
        """Label one sub-requirement from extracted facts, derived facts, and citations."""
