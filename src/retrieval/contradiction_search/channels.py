"""Channel query text.

Support search looks for facts that could establish the requirement.
Contradiction search looks for facts that could refute it.
"""

from __future__ import annotations

from src.retrieval.query_models.models import RetrievalHints, RetrievalQuery


def support_query_terms(query: RetrievalQuery) -> tuple:
    hints = query.hints
    return _present(
        hints.concept,
        hints.body_part,
        hints.laterality,
        *hints.relevant_concepts,
        *hints.supporting_patterns,
        *hints.likely_notes,
    )


def contradiction_query_terms(query: RetrievalQuery) -> tuple:
    hints = query.hints
    return _present(
        hints.concept,
        hints.body_part,
        hints.laterality,
        *hints.relevant_concepts,
        *hints.contradictory_patterns,
    )


def support_query_text(hints: RetrievalHints) -> str:
    return " ".join(
        _present(
            hints.concept,
            *hints.relevant_concepts,
            *hints.supporting_patterns,
            *hints.likely_notes,
        )
    )


def contradiction_query_text(hints: RetrievalHints) -> str:
    return " ".join(
        _present(
            hints.concept,
            *hints.relevant_concepts,
            *hints.contradictory_patterns,
        )
    )


def _present(*values: str) -> tuple:
    items = []
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            items.append(text)
    return tuple(items)
