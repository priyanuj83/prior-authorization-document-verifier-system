"""Atomic sub-requirement models.

A policy criterion is decomposed once per policy version into reusable
atomic sub-requirements. This persisted representation is the source of
truth for verification, not a per-case cache.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

from src.requirement_models.semantics import PolicySemantics


@dataclass(frozen=True)
class AtomicSubRequirement:
    criterion_id: str
    sub_requirement_id: str
    text: str
    semantics: PolicySemantics = field(default_factory=PolicySemantics)


@dataclass(frozen=True)
class DecomposedCriterion:
    criterion_id: str
    criterion_text: str
    sub_requirements: Tuple[AtomicSubRequirement, ...]


@dataclass(frozen=True)
class DecomposedPolicy:
    """Version-specific structured requirements used by the verifier."""

    policy_id: str
    version: str
    criteria: Tuple[DecomposedCriterion, ...]

    def all_sub_requirements(self) -> Tuple[AtomicSubRequirement, ...]:
        items = []
        for criterion in self.criteria:
            items.extend(criterion.sub_requirements)
        return tuple(items)
