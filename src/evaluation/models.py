"""Gold evaluation models.

These objects are hidden from the verifier. Only evaluation code may
construct them, and only from gold/ files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Tuple


@dataclass(frozen=True)
class GoldCriterionLabel:
    id: str
    label: str
    reasoning: Optional[str] = None


@dataclass(frozen=True)
class GoldLabels:
    case_id: str
    policy_id: Optional[str]
    policy_version: Optional[str]
    criteria: Tuple[GoldCriterionLabel, ...]
    provider_documentation_status: Optional[str] = None
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GoldEvaluationPacket:
    """Hidden evaluation artifacts for one case. Never passed to the verifier."""

    case_id: str
    labels: GoldLabels
    ledger: Optional[Mapping[str, Any]] = None
    generation_plan: Optional[Mapping[str, Any]] = None
