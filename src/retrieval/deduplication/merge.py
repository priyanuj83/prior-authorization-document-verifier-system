"""Merge support and contradiction hits, then collapse duplicate chunks."""

from __future__ import annotations

from typing import Dict, Sequence, Tuple

from src.enums import RetrievalChannel
from src.retrieval.query_models.models import EvidenceCandidate


def merge_and_deduplicate(
    support_candidates: Sequence[EvidenceCandidate],
    contradiction_candidates: Sequence[EvidenceCandidate],
) -> Tuple[EvidenceCandidate, ...]:
    """One chunk that hits both channels is kept once, with both signal sets."""

    merged: Dict[str, EvidenceCandidate] = {}
    for candidate in support_candidates:
        merged[candidate.chunk_id] = _with_channel(candidate, RetrievalChannel.SUPPORT)
    for candidate in contradiction_candidates:
        existing = merged.get(candidate.chunk_id)
        if existing is None:
            merged[candidate.chunk_id] = _with_channel(
                candidate, RetrievalChannel.CONTRADICTION
            )
            continue
        merged[candidate.chunk_id] = _combine(existing, candidate)
    return tuple(merged.values())


def _with_channel(
    candidate: EvidenceCandidate, channel: RetrievalChannel
) -> EvidenceCandidate:
    support_signals = candidate.retrieval_signals if channel is RetrievalChannel.SUPPORT else None
    contradiction_signals = (
        candidate.retrieval_signals if channel is RetrievalChannel.CONTRADICTION else None
    )
    return EvidenceCandidate(
        note_id=candidate.note_id,
        chunk_id=candidate.chunk_id,
        source_file=candidate.source_file,
        section=candidate.section,
        note_date=candidate.note_date,
        evidence_scope=candidate.evidence_scope,
        text=candidate.text,
        retrieval_score=candidate.retrieval_score,
        retrieval_signals=candidate.retrieval_signals,
        channels=(channel,),
        case_id=candidate.case_id,
        patient_id=candidate.patient_id,
        body_part=candidate.body_part,
        laterality=candidate.laterality,
        note_type=candidate.note_type,
        support_signals=support_signals,
        contradiction_signals=contradiction_signals,
    )


def _combine(support: EvidenceCandidate, contradiction: EvidenceCandidate) -> EvidenceCandidate:
    if contradiction.retrieval_score > support.retrieval_score:
        signals = contradiction.retrieval_signals
    else:
        signals = support.retrieval_signals
    return EvidenceCandidate(
        note_id=support.note_id,
        chunk_id=support.chunk_id,
        source_file=support.source_file,
        section=support.section,
        note_date=support.note_date,
        evidence_scope=support.evidence_scope,
        text=support.text,
        retrieval_score=max(support.retrieval_score, contradiction.retrieval_score),
        retrieval_signals=signals,
        channels=(RetrievalChannel.SUPPORT, RetrievalChannel.CONTRADICTION),
        case_id=support.case_id,
        patient_id=support.patient_id,
        body_part=support.body_part,
        laterality=support.laterality,
        note_type=support.note_type,
        support_signals=support.support_signals,
        contradiction_signals=contradiction.retrieval_signals,
    )
