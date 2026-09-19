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
