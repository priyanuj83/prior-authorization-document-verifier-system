"""Hard filters versus ranking signals.

Hard filters are only applied when exclusion is safe:
- patient id must match,
- evidence scope must match,
- case id matches only for the submitted-packet search,
- a date window is applied only when the policy marks it as a hard filter.

Unknown laterality, body part, and note type are ranking signals, not filters.
"""

from __future__ import annotations

from typing import Optional

from src.indexing.index_writer.memory import IndexedChunk
from src.retrieval.query_models.models import RetrievalQuery


def passes_hard_filters(chunk: IndexedChunk, query: RetrievalQuery) -> bool:
    if chunk.patient_id != query.context.patient_id:
        return False
    if chunk.evidence_scope is not query.evidence_scope:
        return False
    if query.restrict_to_case and chunk.case_id != query.context.case_id:
        return False
    if query.hints.hard_date_filter and not _inside_hard_window(chunk, query):
        return False
    return True


def _inside_hard_window(chunk: IndexedChunk, query: RetrievalQuery) -> bool:
    """Unknown dates stay in the set. Dropping them would not be a safe exclusion."""

    if chunk.note_date is None:
        return True
    window = query.hints.relevant_date_range
    if window.start is not None and chunk.note_date < window.start:
        return False
    if window.end is not None and chunk.note_date > window.end:
        return False
    return True


def tri_state_match(expected: Optional[str], actual: Optional[str]) -> Optional[bool]:
    """Null on either side means unknown, not a mismatch."""

    if not expected or not actual:
        return None
    return expected.strip().lower() == actual.strip().lower()


def note_type_match(likely_notes: tuple, note_type: Optional[str]) -> Optional[bool]:
    if not likely_notes or not note_type:
        return None
    actual = note_type.lower()
    for hint in likely_notes:
        lowered = hint.lower()
        if lowered in actual or actual in lowered:
            return True
    return False
