"""Retrieval evaluation hooks.

Callers pass gold filenames in. These functions do not open gold/ and do
not import the evaluation package.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from src.enums import RetrievalFailureCategory


@dataclass(frozen=True)
class RetrievalEvalResult:
    evidence_note_recall: float
    recall_at_k: Optional[float]
    retrieved_files: tuple
    gold_files: tuple
    failure_category: Optional[RetrievalFailureCategory]


def evidence_note_recall(retrieved_files: Sequence[str], gold_files: Sequence[str]) -> float:
    """Share of gold evidence notes present anywhere in the candidate set."""

    if not gold_files:
        raise ValueError("gold_files must name the evidence notes to recall")
    retrieved = {_name(path) for path in retrieved_files}
    gold = {_name(path) for path in gold_files}
    return len(retrieved & gold) / len(gold)


def recall_at_k(
    retrieved_files: Sequence[str],
    gold_files: Sequence[str],
    k: int,
) -> float:
    if k < 1:
        raise ValueError("k must be positive")
    return evidence_note_recall(list(retrieved_files)[:k], gold_files)


def categorize_failure(
    *,
    gold_files: Sequence[str],
    retrieved_files: Sequence[str],
    extraction_correct: bool,
    temporal_correct: bool,
    verification_correct: bool,
) -> Optional[RetrievalFailureCategory]:
    """Assign the earliest pipeline stage that explains a wrong outcome."""

    if evidence_note_recall(retrieved_files, gold_files) < 1.0:
        return RetrievalFailureCategory.RETRIEVAL_MISS
    if not extraction_correct:
        return RetrievalFailureCategory.EXTRACTION_ERROR
    if not temporal_correct:
        return RetrievalFailureCategory.TEMPORAL_REASONING_ERROR
    if not verification_correct:
        return RetrievalFailureCategory.VERIFICATION_ERROR
    return None


def _name(path: str) -> str:
    return Path(path).name
