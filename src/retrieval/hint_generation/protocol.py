"""Retrieval hint generator.

The generator interprets the atomic requirement and neutral case context.
It does not search notes, rank documents, or assign evidence labels.
"""

from __future__ import annotations

from typing import Protocol

from src.requirement_models.models import AtomicSubRequirement
from src.retrieval.query_models.models import NeutralCaseContext, RetrievalHints


class RetrievalHintGenerator(Protocol):
    def generate(
        self,
        requirement: AtomicSubRequirement,
        context: NeutralCaseContext,
    ) -> RetrievalHints:
        """Return semantic search hints only."""
