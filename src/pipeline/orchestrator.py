"""Orchestrate the designed verifier workflow.

Order:
    case load -> policy resolution -> (if resolved) decompose ->
    atomic verify -> criterion aggregate -> case aggregate

This module wires components. Deterministic rules live in their own
packages. Retrieval and model-backed verification remain placeholders.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from src.atomic_verification.placeholder import PlaceholderAtomicVerifier
from src.atomic_verification.protocol import AtomicVerifier
from src.case_aggregation.aggregator import aggregate_case
from src.case_loading.loader import load_case, load_case_dir
from src.case_loading.models import VerifierCaseInput
from src.common.paths import CASES_DIR
from src.criterion_aggregation.aggregator import aggregate_criterion
from src.criterion_aggregation.models import CriterionAggregationResult
from src.enums import PolicyResolverAction, PolicyResolverStatus
from src.pipeline.models import CaseVerificationResult
from src.policy_decomposition.placeholder import PlaceholderPolicyDecomposer
from src.policy_decomposition.protocol import DecomposedPolicyStore, PolicyDecomposer
from src.policy_decomposition.store import InMemoryDecomposedPolicyStore
from src.policy_models.repository import FilesystemPolicyRepository, PolicyRepository
from src.policy_resolution.models import PolicyResolutionRequest
from src.policy_resolution.protocol import PolicyResolver
from src.policy_resolution.resolver import CatalogPolicyResolver
from src.requirement_models.models import DecomposedPolicy


class EvidenceVerifierPipeline:
    def __init__(
        self,
        repository: Optional[PolicyRepository] = None,
        resolver: Optional[PolicyResolver] = None,
        decomposer: Optional[PolicyDecomposer] = None,
        decomposed_store: Optional[DecomposedPolicyStore] = None,
        atomic_verifier: Optional[AtomicVerifier] = None,
        cases_dir: Path = CASES_DIR,
    ) -> None:
        self._repository = repository or FilesystemPolicyRepository()
        self._resolver = resolver or CatalogPolicyResolver(self._repository)
        self._decomposer = decomposer or PlaceholderPolicyDecomposer()
        self._decomposed_store = decomposed_store or InMemoryDecomposedPolicyStore()
        self._atomic_verifier = atomic_verifier or PlaceholderAtomicVerifier()
        self._cases_dir = Path(cases_dir)

    def run_case(self, case_id: str) -> CaseVerificationResult:
        case_input = load_case(case_id, cases_dir=self._cases_dir)
        return self.run(case_input)

    def run_case_dir(self, case_dir: Path) -> CaseVerificationResult:
        case_input = load_case_dir(Path(case_dir))
        return self.run(case_input)

    def run(self, case_input: VerifierCaseInput) -> CaseVerificationResult:
        request = case_input.pa_request
        resolution = self._resolver.resolve(
            PolicyResolutionRequest(
                plan_id=request.plan_id,
                service_key=request.service_key,
                submitted_date=request.submitted_date,
            )
        )

        if resolution.status is not PolicyResolverStatus.RESOLVED:
            return CaseVerificationResult(
                case_id=case_input.case_id,
                policy_resolution=resolution,
                overall_status=None,
                criteria=(),
                recommended_action=PolicyResolverAction.MANUAL_REVIEW,
                missing_criterion_ids=(),
                contradicted_criterion_ids=(),
                rationale=resolution.status_rationale,
                case_input=case_input,
            )

        selected = resolution.selected_version
        if selected is None:
            raise RuntimeError("RESOLVED policy result is missing its candidate")

        document = self._repository.get_document(selected.policy_id, selected.version)
        decomposed = self._get_or_decompose(document.policy_id, document.version, document)
        criteria = self._verify_criteria(decomposed, case_input)
        aggregated = aggregate_case(criteria)
        return CaseVerificationResult(
            case_id=case_input.case_id,
            policy_resolution=resolution,
            overall_status=aggregated.overall_status,
            criteria=aggregated.criterion_results,
            recommended_action=PolicyResolverAction.START_VERIFICATION,
            missing_criterion_ids=aggregated.missing_criterion_ids,
            contradicted_criterion_ids=aggregated.contradicted_criterion_ids,
            rationale=aggregated.rationale,
            decomposed_policy=decomposed,
            case_aggregation=aggregated,
            case_input=case_input,
        )

    def _get_or_decompose(
        self,
        policy_id: str,
        version: str,
        document,
    ) -> DecomposedPolicy:
        existing = self._decomposed_store.get(policy_id, version)
        if existing is not None:
            return existing
        decomposed = self._decomposer.decompose(document)
        self._decomposed_store.put(decomposed)
        return decomposed

    def _verify_criteria(
        self,
        decomposed: DecomposedPolicy,
        case_input: VerifierCaseInput,
    ) -> List[CriterionAggregationResult]:
        results: List[CriterionAggregationResult] = []
        for criterion in decomposed.criteria:
            sub_outputs = [
                self._atomic_verifier.verify(
                    sub_requirement,
                    case_input.notes,
                    case_input.pa_request,
                )
                for sub_requirement in criterion.sub_requirements
            ]
            results.append(
                aggregate_criterion(
                    criterion.criterion_id,
                    criterion.criterion_text,
                    sub_outputs,
                )
            )
        return results
