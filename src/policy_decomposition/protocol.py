"""Policy decomposition protocols.

Criteria are decomposed once per policy version into reusable atomic
sub-requirements. Retrieval and LLM strategy for decomposition are not
designed yet; this package only defines the boundary and a placeholder.
"""

from __future__ import annotations

from typing import Optional, Protocol

from src.policy_models.models import PolicyDocument
from src.requirement_models.models import DecomposedPolicy


class PolicyDecomposer(Protocol):
    def decompose(self, policy: PolicyDocument) -> DecomposedPolicy:
        """Produce a persisted structured requirement representation."""


class DecomposedPolicyStore(Protocol):
    def get(self, policy_id: str, version: str) -> Optional[DecomposedPolicy]:
        """Return a previously persisted decomposition, if any."""

    def put(self, policy: DecomposedPolicy) -> None:
        """Persist a version-specific decomposed policy as source of truth."""
