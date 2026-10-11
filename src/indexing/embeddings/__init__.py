"""Embedding provider boundary."""

from src.indexing.embeddings.placeholder import NullEmbeddingProvider
from src.indexing.embeddings.protocol import EmbeddingProvider, cosine_similarity

__all__ = ["EmbeddingProvider", "NullEmbeddingProvider", "cosine_similarity"]
