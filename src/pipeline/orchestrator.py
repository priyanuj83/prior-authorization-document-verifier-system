"""Orchestrate the designed verifier workflow.

Order:
    case load -> policy resolution -> (if resolved) decompose ->
    retrieval hints -> hybrid retrieval -> fact extraction ->
    deterministic reasoning -> atomic verify -> evidence-scope follow-up ->
    criterion aggregate -> case aggregate

Attestation checks run after verification and are not retrieval hints.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from src.atomic_verification.placeholder import PlaceholderAtomicVerifier
from src.atomic_verification.protocol import AtomicVerifier
from src.attestation_verification.placeholder import PlaceholderAttestationVerifier
from src.attestation_verification.protocol import AttestationVerifier
from src.case_aggregation.aggregator import aggregate_case
from src.case_loading.loader import load_case, load_case_dir
from src.case_loading.models import ClinicalNote, VerifierCaseInput
from src.common.paths import CASES_DIR
from src.criterion_aggregation.aggregator import aggregate_criterion
from src.criterion_aggregation.models import CriterionAggregationResult
from src.enums import PolicyResolverAction, PolicyResolverStatus
from src.pipeline.models import CaseVerificationResult, SubRequirementTrace
from src.policy_decomposition.placeholder import PlaceholderPolicyDecomposer
from src.policy_decomposition.protocol import DecomposedPolicyStore, PolicyDecomposer
from src.policy_decomposition.store import InMemoryDecomposedPolicyStore
from src.policy_models.repository import FilesystemPolicyRepository, PolicyRepository
from src.policy_resolution.models import PolicyResolutionRequest
from src.policy_resolution.protocol import PolicyResolver
from src.policy_resolution.resolver import CatalogPolicyResolver
from src.requirement_models.models import DecomposedPolicy
from src.retrieval.coordinator import EvidenceRetrievalCoordinator


class EvidenceVerifierPipeline:
    def __init__(
        self,
        repository: Optional[PolicyRepository] = None,
        resolver: Optional[PolicyResolver] = None,
        decomposer: Optional[PolicyDecomposer] = None,
        decomposed_store: Optional[DecomposedPolicyStore] = None,
        atomic_verifier: Optional[AtomicVerifier] = None,
        retrieval: Optional[EvidenceRetrievalCoordinator] = None,
        attestation_verifier: Optional[AttestationVerifier] = None,
        cases_dir: Path = CASES_DIR,
    ) -> None:
        self._repository = repository or FilesystemPolicyRepository()
        self._resolver = resolver or CatalogPolicyResolver(self._repository)
        self._decomposer = decomposer or PlaceholderPolicyDecomposer()
        self._decomposed_store = decomposed_store or InMemoryDecomposedPolicyStore()
        self._atomic_verifier = atomic_verifier or PlaceholderAtomicVerifier()
        self._retrieval = retrieval or EvidenceRetrievalCoordinator()
        self._attestation_verifier = attestation_verifier or PlaceholderAttestationVerifier()
        self._cases_dir = Path(cases_dir)

    def run_case(
        self,
        case_id: str,
        ehr_notes: Sequence[ClinicalNote] = (),
    ) -> CaseVerificationResult:
        case_input = load_case(case_id, cases_dir=self._cases_dir)
        return self.run(case_input, ehr_notes=ehr_notes)

    def run_case_dir(
        self,
        case_dir: Path,
        ehr_notes: Sequence[ClinicalNote] = (),
    ) -> CaseVerificationResult:
        case_input = load_case_dir(Path(case_dir))
        return self.run(case_input, ehr_notes=ehr_notes)

    def run(
        self,
        case_input: VerifierCaseInput,
        ehr_notes: Sequence[ClinicalNote] = (),
    ) -> CaseVerificationResult:
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
        criteria, traces = self._verify_criteria(decomposed, case_input, ehr_notes)
        aggregated = aggregate_case(criteria)
        attestation_checks = self._attestation_verifier.check(
            request.attestations,
            decomposed.all_sub_requirements(),
        )
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
            retrieval_traces=tuple(traces),
            attestation_checks=tuple(attestation_checks),
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
        ehr_notes: Sequence[ClinicalNote],
    ) -> Tuple[List[CriterionAggregationResult], List[SubRequirementTrace]]:
        evidence_method = getattr(self._atomic_verifier, "verify_from_evidence", None)
        session = None
        if evidence_method is not None:
            session = self._retrieval.prepare_case(case_input, ehr_notes=ehr_notes)

        results: List[CriterionAggregationResult] = []
        traces: List[SubRequirementTrace] = []
        for criterion in decomposed.criteria:
            sub_outputs = []
            for sub_requirement in criterion.sub_requirements:
                if session is not None and evidence_method is not None:
                    prepared = session.prepare(sub_requirement)
                    output = evidence_method(
                        sub_requirement,
                        prepared.facts,
                        prepared.derived,
                        prepared.evidence,
                    )
                    traces.append(
                        SubRequirementTrace(
                            sub_requirement_id=sub_requirement.sub_requirement_id,
                            hints=prepared.hints,
                            evidence=prepared.evidence,
                            follow_up=session.follow_up(
                                output.output_label,
                                prepared.hints,
                            ),
                        )
                    )
                else:
                    output = self._atomic_verifier.verify(
                        sub_requirement,
                        case_input.notes,
                        case_input.pa_request,
                    )
                sub_outputs.append(output)
            results.append(
                aggregate_criterion(
                    criterion.criterion_id,
                    criterion.criterion_text,
                    sub_outputs,
                )
            )
        return results, traces
