"""Structured clinical events produced by fact extraction.

Unknown fields stay null. The extractor must not fill them by guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Tuple

from src.clinical_extraction.evidence_state_models.states import FactValue
from src.enums import EvidenceState


@dataclass(frozen=True)
class ClinicalEvent:
    source_file: str
    evidence: str
    extraction_rationale: str
    section: str = ""
    evidence_state: EvidenceState = EvidenceState.NOT_MENTIONED
    event_date: Optional[date] = None
    event_type: Optional[str] = None
    treatment_type: Optional[str] = None
    body_part: Optional[str] = None
    laterality: Optional[str] = None
    attendance_status: Optional[str] = None
    supervised: Optional[FactValue] = None
    gap_present: Optional[bool] = None
    gap_start_date: Optional[date] = None
    gap_end_date: Optional[date] = None
    gap_duration_days: Optional[int] = None
    resumed_after_gap: Optional[bool] = None
    # True only when the source text explicitly conflicts with the requirement.
    conflicts_with_requirement: bool = False


@dataclass(frozen=True)
class StructuredClinicalFacts:
    events: Tuple[ClinicalEvent, ...]
