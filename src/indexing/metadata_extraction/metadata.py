"""Metadata attached to a note before chunking.

Unknown laterality and body part stay null. Null means unknown, not a mismatch.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from src.common.dates import parse_date
from src.enums import EvidenceScope
from src.indexing.note_parser.parser import ParsedNote

_NOTE_TYPE_HINTS = (
    ("physiotherapy", "physical therapy note"),
    ("physical therapy", "physical therapy note"),
    ("rehabilitation", "rehabilitation note"),
    ("emergency", "emergency department note"),
    ("orthop", "orthopedic note"),
    ("mri", "mri report"),
    ("radiol", "radiology report"),
    ("x-ray", "xray report"),
    ("xray", "xray report"),
)


@dataclass(frozen=True)
class NoteMetadata:
    case_id: str
    patient_id: str
    note_id: str
    note_date: Optional[date]
    note_type: Optional[str]
    body_part: Optional[str]
    laterality: Optional[str]
    source_file: str
    evidence_scope: EvidenceScope


def extract_metadata(
    parsed: ParsedNote,
    *,
    case_id: str,
    patient_id: str,
    source_file: str,
    evidence_scope: EvidenceScope,
    fallback_note_id: str,
) -> NoteMetadata:
    """Build metadata from front matter plus the packet identity.

    case_id and patient_id come from the case being indexed, so a note
    cannot reassign itself to another patient. Laterality and body part
    are taken only from explicit front-matter fields.
    """

    front = parsed.front_matter
    note_id = str(front.get("note_id") or fallback_note_id)
    setting = front.get("setting")
    return NoteMetadata(
        case_id=case_id,
        patient_id=patient_id,
        note_id=note_id,
        note_date=parse_date(front.get("date")),
        note_type=_note_type_from_setting(setting),
        body_part=_optional_text(front.get("body_part")),
        laterality=_optional_text(front.get("laterality")),
        source_file=source_file,
        evidence_scope=evidence_scope,
    )


def _note_type_from_setting(setting) -> Optional[str]:
    if not setting:
        return None
    lowered = str(setting).lower()
    for needle, label in _NOTE_TYPE_HINTS:
        if needle in lowered:
            return label
    return None


def _optional_text(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
