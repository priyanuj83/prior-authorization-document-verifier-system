"""Reranker boundary.

Production weights and cutoffs are not fixed. The default reranker keeps
the full candidate set, ordered by the unweighted retrieval score, because
missing a critical note is worse than keeping an extra one.
"""

from __future__ import annotations

from typing import Optional, Protocol, Sequence, Tuple

from src.retrieval.query_models.models import EvidenceCandidate


class Reranker(Protocol):
    def rerank(
        self, candidates: Sequence[EvidenceCandidate]
    ) -> Tuple[EvidenceCandidate, ...]:
        """Return candidates in display order. Must not assign evidence labels."""


class PassthroughReranker:
    def __init__(self, candidate_limit: Optional[int] = None) -> None:
        if candidate_limit is not None and candidate_limit < 1:
            raise ValueError("candidate_limit must be positive when set")
        self._candidate_limit = candidate_limit

    def rerank(
        self, candidates: Sequence[EvidenceCandidate]
    ) -> Tuple[EvidenceCandidate, ...]:
        ordered = tuple(
            sorted(candidates, key=lambda item: item.retrieval_score, reverse=True)
        )
        if self._candidate_limit is None:
            return ordered
        return ordered[: self._candidate_limit]
