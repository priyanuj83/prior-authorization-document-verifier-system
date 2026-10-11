"""Placeholder hint generator.

Copies persisted policy semantics and neutral case context into the hint
schema. It does not call a model and it never sees attestations or notes.
A later LLM generator can replace this class behind the same protocol.
"""

from __future__ import annotations

from src.requirement_models.models import AtomicSubRequirement
from src.retrieval.hint_generation.context import date_range_for
from src.retrieval.query_models.models import NeutralCaseContext, RetrievalHints


class PlaceholderRetrievalHintGenerator:
    def generate(
        self,
        requirement: AtomicSubRequirement,
        context: NeutralCaseContext,
    ) -> RetrievalHints:
        semantics = requirement.semantics
        return RetrievalHints(
            concept=requirement.text,
            body_part=context.body_part,
            laterality=context.laterality,
            relevant_concepts=semantics.required_facts,
            relevant_date_range=date_range_for(context, requirement),
            likely_notes=(),
            supporting_patterns=semantics.supporting_patterns,
            contradictory_patterns=semantics.refuting_conditions,
            hard_date_filter=semantics.hard_date_filter,
        )
