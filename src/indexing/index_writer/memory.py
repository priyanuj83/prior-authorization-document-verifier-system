"""Replaceable clinical-note index.

The datastore is not chosen. This in-memory index stores raw text,
metadata, and an optional embedding so lexical and vector adapters can
run without Postgres or a vector database.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Protocol, Sequence, Tuple

from src.enums import EvidenceScope


@dataclass(frozen=True)
class IndexedChunk:
    chunk_id: str
    note_id: str
    case_id: str
    patient_id: str
    source_file: str
    note_date: Optional[date]
    note_type: Optional[str]
    section: str
    body_part: Optional[str]
    laterality: Optional[str]
    evidence_scope: EvidenceScope
    text: str
    embedding: Tuple[float, ...]


class ClinicalIndex(Protocol):
    def add(self, chunk: IndexedChunk) -> None:
        """Store one chunk."""

    def chunks(self) -> Sequence[IndexedChunk]:
        """Return every stored chunk. Search applies its own filters."""


class InMemoryClinicalIndex:
    def __init__(self) -> None:
        self._chunks: list = []

    def add(self, chunk: IndexedChunk) -> None:
        self._chunks.append(chunk)

    def chunks(self) -> Sequence[IndexedChunk]:
        return tuple(self._chunks)
