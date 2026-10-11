"""Index submitted notes or other provider documents.

Gold evaluation paths are refused before any chunk is stored.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

from src.case_loading.boundary import assert_not_hidden_evaluation_path
from src.case_loading.models import ClinicalNote
from src.enums import EvidenceScope
from src.indexing.chunking.chunker import chunk_note_body
from src.indexing.embeddings.placeholder import NullEmbeddingProvider
from src.indexing.embeddings.protocol import EmbeddingProvider
from src.indexing.index_writer.memory import IndexedChunk, InMemoryClinicalIndex
from src.indexing.metadata_extraction.metadata import extract_metadata
from src.indexing.note_parser.parser import parse_note


def index_clinical_notes(
    notes: Sequence[ClinicalNote],
    *,
    case_id: str,
    patient_id: str,
    evidence_scope: EvidenceScope,
    embedder: Optional[EmbeddingProvider] = None,
    index: Optional[InMemoryClinicalIndex] = None,
) -> InMemoryClinicalIndex:
    """Parse, chunk, embed, and store notes for one patient and scope."""

    target = index or InMemoryClinicalIndex()
    vectorizer = embedder or NullEmbeddingProvider()
    for note in notes:
        assert_not_hidden_evaluation_path(Path(note.path), context="Indexer")
        assert_not_hidden_evaluation_path(Path(note.file), context="Indexer")
        parsed = parse_note(note.content)
        metadata = extract_metadata(
            parsed,
            case_id=case_id,
            patient_id=patient_id,
            source_file=note.path or note.file,
            evidence_scope=evidence_scope,
            fallback_note_id=Path(note.file).stem,
        )
        for chunk in chunk_note_body(parsed.body):
            target.add(
                IndexedChunk(
                    chunk_id=f"{metadata.note_id}:{chunk.index}",
                    note_id=metadata.note_id,
                    case_id=metadata.case_id,
                    patient_id=metadata.patient_id,
                    source_file=metadata.source_file,
                    note_date=metadata.note_date,
                    note_type=metadata.note_type,
                    section=chunk.section,
                    body_part=metadata.body_part,
                    laterality=metadata.laterality,
                    evidence_scope=metadata.evidence_scope,
                    text=chunk.text,
                    embedding=tuple(vectorizer.embed(chunk.text)),
                )
            )
    return target
