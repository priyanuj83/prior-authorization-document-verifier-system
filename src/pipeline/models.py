"""User-facing end-to-end verification result."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from src.attestation_verification.models import AttestationCheck
from src.case_aggregation.models import CaseAggregationResult
from src.case_loading.models import VerifierCaseInput
from src.criterion_aggregation.models import CriterionAggregationResult
from src.enums import CaseStatus, PolicyResolverAction
from src.policy_resolution.models import PolicyResolutionResult
from src.requirement_models.models import DecomposedPolicy
from src.retrieval.query_models.models import CandidateEvidenceSet, RetrievalHints
from src.retrieval.scope_follow_up.follow_up import ScopeFollowUp


@dataclass(frozen=True)
class SubRequirementTrace:
    """Retrieval and follow-up for one atomic sub-requirement. Not a label."""

    sub_requirement_id: str
    hints: RetrievalHints
    evidence: CandidateEvidenceSet
    follow_up: ScopeFollowUp


@dataclass(frozen=True)
class CaseVerificationResult:
    """Structured output of the current end-to-end contract."""

    case_id: str
    policy_resolution: PolicyResolutionResult
    overall_status: Optional[CaseStatus]
    criteria: Tuple[CriterionAggregationResult, ...]
    recommended_action: PolicyResolverAction
    missing_criterion_ids: Tuple[str, ...]
    contradicted_criterion_ids: Tuple[str, ...]
    rationale: str
    decomposed_policy: Optional[DecomposedPolicy] = None
    case_aggregation: Optional[CaseAggregationResult] = None
    case_input: Optional[VerifierCaseInput] = None
    retrieval_traces: Tuple[SubRequirementTrace, ...] = ()
    attestation_checks: Tuple[AttestationCheck, ...] = ()
