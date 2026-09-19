"""Policy resolver input and output contracts.

The schema shape is the same for RESOLVED, UNRESOLVED, and MULTIPLE_MATCHES.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Tuple

from src.enums import PolicyResolverAction, PolicyResolverStatus
from src.policy_models.models import PolicyVersion


@dataclass(frozen=True)
class PolicyResolutionRequest:
    plan_id: str
    service_key: str
    submitted_date: date


@dataclass(frozen=True)
class PolicyResolutionResult:
    status: PolicyResolverStatus
    submission_date: date
    candidates: Tuple[PolicyVersion, ...]
    status_rationale: str
    recommended_action: PolicyResolverAction

    @property
    def selected_version(self) -> Optional[PolicyVersion]:
        if self.status is PolicyResolverStatus.RESOLVED and len(self.candidates) == 1:
            return self.candidates[0]
        return None
