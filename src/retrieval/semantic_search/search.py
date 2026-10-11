"""Semantic search adapter.

Similarity is a candidate signal. It does not decide PROVEN, NOT_PROVEN,
or REFUTED.
"""

from __future__ import annotations

from src.indexing.embeddings.protocol import EmbeddingProvider, cosine_similarity
from src.indexing.index_writer.memory import IndexedChunk


class SemanticSearcher:
    def __init__(self, embedder: EmbeddingProvider) -> None:
        self._embedder = embedder

    def score(self, query_text: str, chunk: IndexedChunk) -> float:
        query_vector = self._embedder.embed(query_text)
        return cosine_similarity(query_vector, chunk.embedding)
