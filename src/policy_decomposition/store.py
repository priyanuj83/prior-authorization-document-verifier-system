"""In-memory decomposed-policy store.

A cache may be added later for performance. The source of truth is this
persisted representation, not a per-patient recomputation.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from src.requirement_models.models import DecomposedPolicy


class InMemoryDecomposedPolicyStore:
    def __init__(self) -> None:
        self._items: Dict[Tuple[str, str], DecomposedPolicy] = {}

    def get(self, policy_id: str, version: str) -> Optional[DecomposedPolicy]:
        return self._items.get((policy_id, version))

    def put(self, policy: DecomposedPolicy) -> None:
        self._items[(policy.policy_id, policy.version)] = policy
