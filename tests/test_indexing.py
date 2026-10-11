from datetime import date

from src.case_loading.models import ClinicalNote
from src.common.exceptions import HiddenEvaluationDataError
from src.common.paths import CASES_DIR
from src.enums import EvidenceScope
from src.indexing import index_clinical_notes
from src.indexing.chunking import chunk_note_body
import pytest


def test_ed_note_chunks_by_section_and_merges_assessment_plan() -> None:
    path = (
        CASES_DIR
        / "KNEE-ARTHRO-0001"
        / "input"
        / "notes"
        / "2014-01-31-ed-visit.md"
    )
    text = path.read_text(encoding="utf-8")
    from src.indexing.note_parser import parse_note

    parsed = parse_note(text)
    sections = [chunk.section for chunk in chunk_note_body(parsed.body)]
    assert "HPI" in sections
    assert "Examination" in sections
    assert "Imaging" in sections
    assert "Assessment / Plan" in sections
    assert "Assessment" not in sections
    assert "Plan" not in sections
    imaging = next(chunk for chunk in chunk_note_body(parsed.body) if chunk.section == "Imaging")
    assert "Kellgren-Lawrence grade 1" in imaging.text


def test_note_without_sections_is_one_chunk() -> None:
    chunks = chunk_note_body("Patient declined physical therapy.")
    assert len(chunks) == 1
    assert chunks[0].section == "document"
    assert chunks[0].text == "Patient declined physical therapy."


def test_index_keeps_provenance_and_refuses_gold() -> None:
    note = ClinicalNote(
        file="2014-01-10-pt.md",
        path="input/notes/2014-01-10-pt.md",
        content="\n".join(
            [
                "---",
                "note_id: N1",
                "date: 2014-01-10",
                "setting: Outpatient Physiotherapy Department",
                "---",
                "",
                "**HPI**",
                "",
                "Initial supervised PT evaluation completed.",
            ]
        ),
    )
    index = index_clinical_notes(
        [note],
        case_id="CASE-1",
        patient_id="PAT-1",
        evidence_scope=EvidenceScope.SUBMITTED_PACKET,
    )
    stored = index.chunks()
    assert len(stored) == 1
    chunk = stored[0]
    assert chunk.case_id == "CASE-1"
    assert chunk.patient_id == "PAT-1"
    assert chunk.note_id == "N1"
    assert chunk.note_date == date(2014, 1, 10)
    assert chunk.note_type == "physical therapy note"
    assert chunk.section == "HPI"
    assert chunk.source_file == "input/notes/2014-01-10-pt.md"
    assert chunk.evidence_scope is EvidenceScope.SUBMITTED_PACKET
    assert chunk.laterality is None
    assert "Initial supervised PT evaluation completed." in chunk.text

    hidden = ClinicalNote(
        file="labels.yaml",
        path="gold/labels.yaml",
        content="secret: 1",
    )
    with pytest.raises(HiddenEvaluationDataError):
        index_clinical_notes(
            [hidden],
            case_id="CASE-1",
            patient_id="PAT-1",
            evidence_scope=EvidenceScope.SUBMITTED_PACKET,
        )
