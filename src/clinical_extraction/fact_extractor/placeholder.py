"""Placeholder fact extractor.

Preserves each retrieved passage and marks clinical fields NOT_MENTIONED.
It does not infer supervision, duration, laterality, or refutation from
keywords. A model-backed extractor can replace it behind the same protocol.
"""

from __future__ import annotations

from src.clinical_extraction.event_models.events import ClinicalEvent, StructuredClinicalFacts
from src.clinical_extraction.evidence_state_models.states import not_mentioned
from src.enums import EvidenceState
from src.requirement_models.models import AtomicSubRequirement
from src.retrieval.query_models.models import CandidateEvidenceSet

_RATIONALE = (
    "Placeholder extraction preserves the source passage and does not infer "
    "facts the text was not interpreted to state."
)


class PlaceholderClinicalFactExtractor:
    def extract(
        self,
        requirement: AtomicSubRequirement,
        evidence: CandidateEvidenceSet,
    ) -> StructuredClinicalFacts:
        del requirement
        events = tuple(
            ClinicalEvent(
                source_file=candidate.source_file,
                section=candidate.section,
                evidence=candidate.text,
                extraction_rationale=_RATIONALE,
                evidence_state=EvidenceState.NOT_MENTIONED,
                supervised=not_mentioned(),
                conflicts_with_requirement=False,
            )
            for candidate in evidence.merged_candidates
        )
        return StructuredClinicalFacts(events=events)
