from src.policy_decomposition import (
    InMemoryDecomposedPolicyStore,
    PlaceholderPolicyDecomposer,
)
from src.policy_models.models import PolicyCriterion, PolicyDocument


def test_placeholder_decomposer_is_identity_and_store_is_version_keyed() -> None:
    document = PolicyDocument(
        policy_id="POL",
        version="1.0",
        title="Test",
        logic="all_of",
        criteria=(
            PolicyCriterion(id="C4", text="At least 6 weeks of supervised physical therapy."),
        ),
    )
    decomposed = PlaceholderPolicyDecomposer().decompose(document)
    assert decomposed.policy_id == "POL"
    assert decomposed.version == "1.0"
    assert decomposed.criteria[0].sub_requirements[0].sub_requirement_id == "C4.1"
    store = InMemoryDecomposedPolicyStore()
    assert store.get("POL", "1.0") is None
    store.put(decomposed)
    assert store.get("POL", "1.0") is decomposed
    assert store.get("POL", "2.0") is None


def test_decomposition_copies_policy_semantics_without_inventing_continuity() -> None:
    from src.policy_models.repository import FilesystemPolicyRepository

    document = FilesystemPolicyRepository().get_document("PA-KNEE-ARTHRO-001", "1.0.0")
    decomposed = PlaceholderPolicyDecomposer().decompose(document)
    therapy = next(
        item
        for item in decomposed.all_sub_requirements()
        if item.criterion_id == "C4_conservative_therapy"
    )
    assert therapy.semantics.calculation_required is True
    assert therapy.semantics.calculation_type == "temporal_duration"
    assert therapy.semantics.threshold_days == 42
    assert therapy.semantics.lookback_days == 365
    assert therapy.semantics.continuity_required is False
    assert therapy.semantics.continuity_max_gap_days is None
    assert therapy.semantics.hard_date_filter is False
    assert any("42" in item for item in therapy.semantics.refuting_conditions)
