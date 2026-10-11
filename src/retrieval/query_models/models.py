"""Retrieval query and candidate schemas.

The same candidate shape is used for support hits, contradiction hits,
and the merged set.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Tuple

from src.enums import EvidenceScope, RetrievalChannel


@dataclass(frozen=True)
class DateRange:
    start: Optional[date] = None
    end: Optional[date] = None


@dataclass(frozen=True)
class NeutralCaseContext:
    """PA-form context that may guide search. Attestations are not included."""

    case_id: str
    patient_id: str
    service_key: str
    requested_service: str
    body_part: Optional[str]
    laterality: Optional[str]
    diagnosis: Optional[str]
    submitted_date: date
    episode_start: Optional[date] = None
    episode_end: Optional[date] = None


@dataclass(frozen=True)
class RetrievalHints:
    """Semantic search hints. Patterns are not evidence."""

    concept: str
    body_part: Optional[str] = None
    laterality: Optional[str] = None
    relevant_concepts: Tuple[str, ...] = ()
    relevant_date_range: DateRange = field(default_factory=DateRange)
    likely_notes: Tuple[str, ...] = ()
    supporting_patterns: Tuple[str, ...] = ()
    contradictory_patterns: Tuple[str, ...] = ()
    hard_date_filter: bool = False


@dataclass(frozen=True)
class RetrievalSignals:
    semantic_similarity: float
    lexical_match: float
    body_part_match: Optional[bool]
    laterality_match: Optional[bool]
    note_type_match: Optional[bool]
    support_pattern_match: Optional[bool]
    contradiction_pattern_match: Optional[bool]


@dataclass(frozen=True)
class EvidenceCandidate:
    note_id: str
    chunk_id: str
    source_file: str
    section: str
    note_date: Optional[date]
    evidence_scope: EvidenceScope
    text: str
    retrieval_score: float
    retrieval_signals: RetrievalSignals
    channels: Tuple[RetrievalChannel, ...]
    case_id: str
    patient_id: str
    body_part: Optional[str] = None
    laterality: Optional[str] = None
    note_type: Optional[str] = None
    support_signals: Optional[RetrievalSignals] = None
    contradiction_signals: Optional[RetrievalSignals] = None


@dataclass(frozen=True)
class CandidateEvidenceSet:
    support_candidates: Tuple[EvidenceCandidate, ...]
    contradiction_candidates: Tuple[EvidenceCandidate, ...]
    merged_candidates: Tuple[EvidenceCandidate, ...]


@dataclass(frozen=True)
class RetrievalQuery:
    context: NeutralCaseContext
    hints: RetrievalHints
    evidence_scope: EvidenceScope
    channels: Tuple[RetrievalChannel, ...] = (
        RetrievalChannel.SUPPORT,
        RetrievalChannel.CONTRADICTION,
    )
    restrict_to_case: bool = True
