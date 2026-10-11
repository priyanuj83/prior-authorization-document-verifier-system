"""Embedding providers.

The embedding model is intentionally not selected. Callers depend on this
protocol so a hosted or local model can replace the placeholder.
"""

from __future__ import annotations

from typing import Protocol, Sequence, Tuple


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> Tuple[float, ...]:
        """Return a vector for text. Empty means this provider has no vector."""


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Cosine similarity in [0, 1] for this corpus of non-negative uses.

    Returns 0 when either vector is missing or the lengths differ. A score
    is a retrieval signal, not evidence that a fact is proven.
    """

    if not left or not right or len(left) != len(right):
        return 0.0
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for left_value, right_value in zip(left, right):
        dot += left_value * right_value
        left_norm += left_value * left_value
        right_norm += right_value * right_value
    if left_norm <= 0.0 or right_norm <= 0.0:
        return 0.0
    score = dot / ((left_norm ** 0.5) * (right_norm ** 0.5))
    if score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0
    return score
