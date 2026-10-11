"""Hybrid retrieval.

Lexical and vector scores are combined with an unweighted sum so no
production weight vector is baked in. Metadata matches are attached as
signals and do not exclude a chunk. Every chunk that passes the hard
filters is returned, so recall is preferred over an early cutoff.
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

from src.enums import RetrievalChannel
from src.indexing.embeddings.placeholder import NullEmbeddingProvider
from src.indexing.embeddings.protocol import EmbeddingProvider
from src.indexing.index_writer.memory import ClinicalIndex, IndexedChunk
from src.retrieval.contradiction_search.channels import (
    contradiction_query_terms,
    contradiction_query_text,
    support_query_terms,
    support_query_text,
)
from src.retrieval.deduplication.merge import merge_and_deduplicate
from src.retrieval.hybrid_search.filters import (
    note_type_match,
    passes_hard_filters,
    tri_state_match,
)
from src.retrieval.lexical_search.search import lexical_score
from src.retrieval.query_models.models import (
    CandidateEvidenceSet,
    EvidenceCandidate,
    RetrievalQuery,
    RetrievalSignals,
)
from src.retrieval.reranking.passthrough import PassthroughReranker, Reranker
from src.retrieval.semantic_search.search import SemanticSearcher


def provisional_retrieval_score(lexical: float, semantic: float) -> float:
    """Unweighted sum used only to order candidates. Not a proof score."""

    return lexical + semantic


class HybridRetriever:
    def __init__(
        self,
        index: ClinicalIndex,
        embedder: Optional[EmbeddingProvider] = None,
        reranker: Optional[Reranker] = None,
    ) -> None:
        self._index = index
        self._semantic = SemanticSearcher(embedder or NullEmbeddingProvider())
        self._reranker = reranker or PassthroughReranker()

    def retrieve(self, query: RetrievalQuery) -> CandidateEvidenceSet:
        eligible = [
            chunk for chunk in self._index.chunks() if passes_hard_filters(chunk, query)
        ]
        support: Tuple[EvidenceCandidate, ...] = ()
        contradiction: Tuple[EvidenceCandidate, ...] = ()
        if RetrievalChannel.SUPPORT in query.channels:
            support = self._score_channel(
                eligible,
                query,
                terms=support_query_terms(query),
                semantic_text=support_query_text(query.hints),
                channel=RetrievalChannel.SUPPORT,
            )
        if RetrievalChannel.CONTRADICTION in query.channels:
            contradiction = self._score_channel(
                eligible,
                query,
                terms=contradiction_query_terms(query),
                semantic_text=contradiction_query_text(query.hints),
                channel=RetrievalChannel.CONTRADICTION,
            )
        merged = self._reranker.rerank(merge_and_deduplicate(support, contradiction))
        return CandidateEvidenceSet(
            support_candidates=support,
            contradiction_candidates=contradiction,
            merged_candidates=merged,
        )

    def _score_channel(
        self,
        chunks: Sequence[IndexedChunk],
        query: RetrievalQuery,
        *,
        terms: Sequence[str],
        semantic_text: str,
        channel: RetrievalChannel,
    ) -> Tuple[EvidenceCandidate, ...]:
        candidates = []
        support_terms = query.hints.supporting_patterns
        contradiction_terms = query.hints.contradictory_patterns
        for chunk in chunks:
            lexical = lexical_score(terms, chunk.text)
            semantic = self._semantic.score(semantic_text, chunk)
            support_flag = _pattern_flag(support_terms, chunk.text)
            contradiction_flag = _pattern_flag(contradiction_terms, chunk.text)
            signals = RetrievalSignals(
                semantic_similarity=semantic,
                lexical_match=lexical,
                body_part_match=tri_state_match(query.hints.body_part, chunk.body_part),
                laterality_match=tri_state_match(query.hints.laterality, chunk.laterality),
                note_type_match=note_type_match(query.hints.likely_notes, chunk.note_type),
                support_pattern_match=support_flag,
                contradiction_pattern_match=contradiction_flag,
            )
            candidates.append(
                EvidenceCandidate(
                    note_id=chunk.note_id,
                    chunk_id=chunk.chunk_id,
                    source_file=chunk.source_file,
                    section=chunk.section,
                    note_date=chunk.note_date,
                    evidence_scope=chunk.evidence_scope,
                    text=chunk.text,
                    retrieval_score=provisional_retrieval_score(lexical, semantic),
                    retrieval_signals=signals,
                    channels=(channel,),
                    case_id=chunk.case_id,
                    patient_id=chunk.patient_id,
                    body_part=chunk.body_part,
                    laterality=chunk.laterality,
                    note_type=chunk.note_type,
                )
            )
        return tuple(sorted(candidates, key=lambda item: item.retrieval_score, reverse=True))


def _pattern_flag(patterns: Sequence[str], text: str):
    if not patterns:
        return None
    return lexical_score(patterns, text) > 0.0
