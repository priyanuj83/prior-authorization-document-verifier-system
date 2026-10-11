"""Clinical fact extractor.

Extraction asks what a note establishes. It does not assign policy labels.
"""

from __future__ import annotations

from typing import Protocol

from src.clinical_extraction.event_models.events import StructuredClinicalFacts
from src.requirement_models.models import AtomicSubRequirement
from src.retrieval.query_models.models import CandidateEvidenceSet


class ClinicalFactExtractor(Protocol):
    def extract(
        self,
        requirement: AtomicSubRequirement,
        evidence: CandidateEvidenceSet,
    ) -> StructuredClinicalFacts:
        """Return grounded facts. Preserve the source passage for each fact."""
