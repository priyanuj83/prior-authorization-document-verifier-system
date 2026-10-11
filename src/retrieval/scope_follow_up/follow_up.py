"""Broader-EHR follow-up after a submitted-packet label.

Suggestions never rewrite PROVEN, NOT_PROVEN, or REFUTED.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from src.enums import AtomicLabel, EvidenceScope, RetrievalChannel
from src.retrieval.hybrid_search.retriever import HybridRetriever
from src.retrieval.query_models.models import EvidenceCandidate, RetrievalQuery


@dataclass(frozen=True)
class ScopeFollowUp:
    submitted_label: AtomicLabel
    ehr_support_suggestions: Tuple[EvidenceCandidate, ...]
    ehr_contradiction_flags: Tuple[EvidenceCandidate, ...]
    message: str


class EvidenceScopeFollowUp:
    def __init__(self, retriever: HybridRetriever) -> None:
        self._retriever = retriever

    def follow_up(self, label: AtomicLabel, query: RetrievalQuery) -> ScopeFollowUp:
        if label is AtomicLabel.NOT_PROVEN:
            evidence = self._retriever.retrieve(
                _scoped(query, EvidenceScope.AVAILABLE_EHR, (RetrievalChannel.SUPPORT,))
            )
            if evidence.support_candidates:
                suggestions = _support_suggestions(evidence.support_candidates)
            else:
                suggestions = ()
            if suggestions:
                message = (
                    "Potential supporting document found in EHR. Consider attaching it. "
                    "This does not change the submitted-packet label to PROVEN."
                )
            else:
                message = (
                    "No additional supporting EHR document was retrieved. "
                    "NOT_PROVEN still describes only the submitted packet."
                )
            return ScopeFollowUp(
                submitted_label=label,
                ehr_support_suggestions=suggestions,
                ehr_contradiction_flags=(),
                message=message,
            )
        if label is AtomicLabel.PROVEN:
            evidence = self._retriever.retrieve(
                _scoped(
                    query,
                    EvidenceScope.AVAILABLE_EHR,
                    (RetrievalChannel.CONTRADICTION,),
                )
            )
            flags = _contradiction_flags(evidence.contradiction_candidates)
            if flags:
                message = (
                    "Targeted EHR contradiction search found candidates that may "
                    "conflict with the submitted packet. They do not silently "
                    "change the submitted-packet label."
                )
            else:
                message = "Targeted EHR contradiction search found no candidates."
            return ScopeFollowUp(
                submitted_label=label,
                ehr_support_suggestions=(),
                ehr_contradiction_flags=flags,
                message=message,
            )
        return ScopeFollowUp(
            submitted_label=label,
            ehr_support_suggestions=(),
            ehr_contradiction_flags=(),
            message=(
                "A clear refutation does not automatically trigger a broader "
                "support search. That reconciliation behavior is not finalized."
            ),
        )


def _support_suggestions(candidates: Tuple[EvidenceCandidate, ...]) -> Tuple[EvidenceCandidate, ...]:
    return tuple(
        candidate
        for candidate in candidates
        if candidate.retrieval_signals.support_pattern_match is True
        or candidate.retrieval_signals.lexical_match > 0.0
        or candidate.retrieval_signals.semantic_similarity > 0.0
    )


def _contradiction_flags(candidates: Tuple[EvidenceCandidate, ...]) -> Tuple[EvidenceCandidate, ...]:
    """Surface EHR notes only when a contradictory pattern actually matches."""

    return tuple(
        candidate
        for candidate in candidates
        if candidate.retrieval_signals.contradiction_pattern_match is True
    )


def _scoped(
    query: RetrievalQuery,
    scope: EvidenceScope,
    channels: Tuple[RetrievalChannel, ...],
) -> RetrievalQuery:
    return RetrievalQuery(
        context=query.context,
        hints=query.hints,
        evidence_scope=scope,
        channels=channels,
        restrict_to_case=False,
    )
