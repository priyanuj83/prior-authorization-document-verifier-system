"""Placeholder embedding provider.

Returns no vector. Semantic search then contributes nothing until a real
embedding model is configured. This is not a clinical embedding model.
"""

from __future__ import annotations

from typing import Tuple


class NullEmbeddingProvider:
    def embed(self, text: str) -> Tuple[float, ...]:
        del text
        return ()
