"""Policy domain models: versioned clinical policies and their criteria.

This layer stores policy identity, effective windows, and structured
criteria. It does not evaluate patient records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Mapping, Optional, Tuple


def _clean_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


@dataclass(frozen=True)
class PolicyVersion:
    """One dated, plan-scoped edition of a clinical policy.

    Used by the Policy Resolver to decide which version applies to a case.
    """

    policy_id: str
    version: str
    plan_id: str
    service_key: str
    effective_from: date
    effective_to: Optional[date] = None

    def as_candidate_dict(self) -> dict:
        return {
            "policy_id": self.policy_id,
            "version": self.version,
            "plan_id": self.plan_id,
            "service_key": self.service_key,
            "effective_from": self.effective_from.isoformat(),
            "effective_to": (
                None if self.effective_to is None else self.effective_to.isoformat()
            ),
        }


@dataclass(frozen=True)
class PolicyCriterion:
    """A single policy criterion as authored in a policy version."""

    id: str
    text: str
    type: Optional[str] = None
    required: bool = True
    branch_id: Optional[str] = None
    waived_if: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", _clean_text(self.text))


@dataclass(frozen=True)
class PolicyWaiver:
    id: str
    text: str
    waives: Tuple[str, ...] = ()
    conditions: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", _clean_text(self.text))


@dataclass(frozen=True)
class PolicyExclusion:
    id: str
    text: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", _clean_text(self.text))


@dataclass(frozen=True)
class PolicyBranch:
    id: str
    text: str
    logic: str
    criterion_ids: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", _clean_text(self.text))


@dataclass(frozen=True)
class PolicyDocument:
    """Full structured policy content for a policy_id + version."""

    policy_id: str
    version: str
    title: str
    logic: str
    criteria: Tuple[PolicyCriterion, ...]
    waivers: Tuple[PolicyWaiver, ...] = ()
    exclusions: Tuple[PolicyExclusion, ...] = ()
    branches: Tuple[PolicyBranch, ...] = ()

    def criterion_by_id(self, criterion_id: str) -> PolicyCriterion:
        for criterion in self.criteria:
            if criterion.id == criterion_id:
                return criterion
        raise KeyError(f"Criterion {criterion_id!r} not found on {self.policy_id}")
