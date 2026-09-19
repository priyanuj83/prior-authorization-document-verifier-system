from datetime import date
from typing import Sequence

from src.atomic_verification.models import AtomicVerifierOutput, NoteEvidence
from src.case_loading.models import ClinicalNote, PriorAuthorizationRequest
from src.enums import AtomicLabel, CaseStatus, PolicyResolverAction, PolicyResolverStatus
from src.pipeline import EvidenceVerifierPipeline
from src.policy_decomposition import (
    InMemoryDecomposedPolicyStore,
    PlaceholderPolicyDecomposer,
)
from src.policy_models.models import PolicyCriterion, PolicyDocument, PolicyVersion
from src.policy_models.repository import InMemoryPolicyRepository
from src.requirement_models.models import AtomicSubRequirement


class ScriptedAtomicVerifier:
    def __init__(self, labels_by_sub_id: dict) -> None:
        self.labels_by_sub_id = labels_by_sub_id

    def verify(
        self,
        sub_requirement: AtomicSubRequirement,
        notes: Sequence[ClinicalNote],
        pa_request: PriorAuthorizationRequest,
    ) -> AtomicVerifierOutput:
        del notes, pa_request
        label = self.labels_by_sub_id[sub_requirement.sub_requirement_id]
        evidence = ()
        if label is AtomicLabel.REFUTED:
            evidence = (
                NoteEvidence(
                    file="example-note.md",
                    evidence="Patient declined physical therapy.",
                    evidence_rationale="Affirmatively indicates PT was not undertaken.",
                ),
            )
        return AtomicVerifierOutput(
            criterion_id=sub_requirement.criterion_id,
            sub_requirement_id=sub_requirement.sub_requirement_id,
            sub_requirement=sub_requirement.text,
            output_label=label,
            rationale="scripted",
            notes=evidence,
        )


def _repo() -> InMemoryPolicyRepository:
    version = PolicyVersion(
        policy_id="POL",
        version="1.0",
        plan_id="HUMANA-COMMERCIAL-01",
        service_key="knee_arthroscopy",
        effective_from=date(2014, 1, 1),
        effective_to=None,
    )
    document = PolicyDocument(
        policy_id="POL",
        version="1.0",
        title="Test policy",
        logic="all_of",
        criteria=(
            PolicyCriterion(id="C1", text="Symptoms are documented."),
            PolicyCriterion(id="C4", text="Physical therapy was completed."),
        ),
    )
    return InMemoryPolicyRepository([version], [document])


def test_pipeline_stops_for_unresolved_policy() -> None:
    repo = InMemoryPolicyRepository(
        [
            PolicyVersion(
                policy_id="POL",
                version="1.0",
                plan_id="HUMANA-COMMERCIAL-01",
                service_key="knee_arthroscopy",
                effective_from=date(2025, 2, 1),
                effective_to=None,
            )
        ]
    )
    pipeline = EvidenceVerifierPipeline(repository=repo)
    result = pipeline.run_case("KNEE-ARTHRO-0001")
    assert result.policy_resolution.status is PolicyResolverStatus.UNRESOLVED
    assert result.recommended_action is PolicyResolverAction.MANUAL_REVIEW
    assert result.overall_status is None
    assert result.criteria == ()


def test_pipeline_placeholder_verifier_yields_documentation_incomplete() -> None:
    pipeline = EvidenceVerifierPipeline()
    result = pipeline.run_case("KNEE-ARTHRO-0001")
    assert result.policy_resolution.status is PolicyResolverStatus.RESOLVED
    assert result.overall_status is CaseStatus.DOCUMENTATION_INCOMPLETE
    assert result.criteria
    assert all(item.label.value == "MISSING" for item in result.criteria)


def test_pipeline_uses_persisted_decomposition_and_scripted_verifier() -> None:
    repo = _repo()
    store = InMemoryDecomposedPolicyStore()
    decomposer = PlaceholderPolicyDecomposer()
    document = repo.get_document("POL", "1.0")
    store.put(decomposer.decompose(document))

    pipeline = EvidenceVerifierPipeline(
        repository=repo,
        decomposed_store=store,
        atomic_verifier=ScriptedAtomicVerifier(
            {
                "C1.1": AtomicLabel.PROVEN,
                "C4.1": AtomicLabel.REFUTED,
            }
        ),
    )
    result = pipeline.run_case("KNEE-ARTHRO-0001")
    assert result.overall_status is CaseStatus.NEEDS_CLINICAL_REVIEW
    assert result.contradicted_criterion_ids == ("C4",)
    asserted = [item for item in result.criteria if item.criterion_id == "C4"][0]
    assert asserted.sub_requirements[0].notes[0].evidence == (
        "Patient declined physical therapy."
    )
