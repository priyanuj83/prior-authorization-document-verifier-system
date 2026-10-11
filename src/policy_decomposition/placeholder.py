"""Placeholder policy decomposer.

LLM-backed decomposition is not designed yet. The placeholder keeps the
pipeline wired by treating each authored criterion as a single atomic
sub-requirement. Real decompositions should replace this and be stored
once per policy version.
"""

from __future__ import annotations

from src.policy_models.models import PolicyDocument
from src.requirement_models.models import (
    AtomicSubRequirement,
    DecomposedCriterion,
    DecomposedPolicy,
)
from src.requirement_models.semantics import semantics_from_criterion


class PlaceholderPolicyDecomposer:
    """Identity decomposition used until a real decomposer is designed."""

    def decompose(self, policy: PolicyDocument) -> DecomposedPolicy:
        criteria = tuple(
            DecomposedCriterion(
                criterion_id=criterion.id,
                criterion_text=criterion.text,
                sub_requirements=(
                    AtomicSubRequirement(
                        criterion_id=criterion.id,
                        sub_requirement_id=f"{criterion.id}.1",
                        text=criterion.text,
                        semantics=semantics_from_criterion(criterion),
                    ),
                ),
            )
            for criterion in policy.criteria
        )
        return DecomposedPolicy(
            policy_id=policy.policy_id,
            version=policy.version,
            criteria=criteria,
        )
