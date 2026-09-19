"""Policy resolver protocol."""

from __future__ import annotations

from typing import Protocol

from src.policy_resolution.models import PolicyResolutionRequest, PolicyResolutionResult


class PolicyResolver(Protocol):
    def resolve(self, request: PolicyResolutionRequest) -> PolicyResolutionResult:
        """Determine which policy version applies to the case."""
