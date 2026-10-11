"""Run hint generation, hybrid retrieval, extraction, and temporal reasoning.

Does not assign the atomic label. The atomic verifier does that next.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from src.case_loading.models import ClinicalNote, VerifierCaseInput
from src.clinical_extraction.event_models.events import StructuredClinicalFacts
from src.clinical_extraction.fact_extractor.placeholder import PlaceholderClinicalFactExtractor
from src.clinical_extraction.fact_extractor.protocol import ClinicalFactExtractor
from src.enums import EvidenceScope
from src.indexing.embeddings.placeholder import NullEmbeddingProvider
from src.indexing.embeddings.protocol import EmbeddingProvider
from src.indexing.pipeline import index_clinical_notes
from src.reasoning.temporal_reasoning.models import DerivedFacts
from src.reasoning.temporal_reasoning.reasoner import TemporalReasoner
from src.requirement_models.models import AtomicSubRequirement
from src.retrieval.hint_generation.context import build_neutral_case_context
from src.retrieval.hint_generation.placeholder import PlaceholderRetrievalHintGenerator
from src.retrieval.hint_generation.protocol import RetrievalHintGenerator
from src.retrieval.hybrid_search.retriever import HybridRetriever
from src.retrieval.query_models.models import (
    CandidateEvidenceSet,
    NeutralCaseContext,
    RetrievalHints,
    RetrievalQuery,
)
from src.retrieval.reranking.passthrough import PassthroughReranker, Reranker
from src.retrieval.scope_follow_up.follow_up import EvidenceScopeFollowUp, ScopeFollowUp


@dataclass(frozen=True)
class PreparedSubRequirement:
    context: NeutralCaseContext
    hints: RetrievalHints
    evidence: CandidateEvidenceSet
    facts: StructuredClinicalFacts
    derived: DerivedFacts


class EvidenceRetrievalCoordinator:
    def __init__(
        self,
        hint_generator: Optional[RetrievalHintGenerator] = None,
        extractor: Optional[ClinicalFactExtractor] = None,
        reasoner: Optional[TemporalReasoner] = None,
        embedder: Optional[EmbeddingProvider] = None,
        reranker: Optional[Reranker] = None,
    ) -> None:
        self._hint_generator = hint_generator or PlaceholderRetrievalHintGenerator()
        self._extractor = extractor or PlaceholderClinicalFactExtractor()
        self._reasoner = reasoner or TemporalReasoner()
        self._embedder = embedder or NullEmbeddingProvider()
        self._reranker = reranker or PassthroughReranker()

    def prepare_case(
        self,
        case_input: VerifierCaseInput,
        ehr_notes: Sequence[ClinicalNote] = (),
    ):
        context = build_neutral_case_context(case_input.case_id, case_input.pa_request)
        index = index_clinical_notes(
            case_input.notes,
            case_id=context.case_id,
            patient_id=context.patient_id,
            evidence_scope=EvidenceScope.SUBMITTED_PACKET,
            embedder=self._embedder,
        )
        if ehr_notes:
            index_clinical_notes(
                ehr_notes,
                case_id=context.case_id,
                patient_id=context.patient_id,
                evidence_scope=EvidenceScope.AVAILABLE_EHR,
                embedder=self._embedder,
                index=index,
            )
        retriever = HybridRetriever(index, embedder=self._embedder, reranker=self._reranker)
        return _CaseRetrievalSession(
            context=context,
            retriever=retriever,
            hint_generator=self._hint_generator,
            extractor=self._extractor,
            reasoner=self._reasoner,
            follow_up=EvidenceScopeFollowUp(retriever),
        )


class _CaseRetrievalSession:
    def __init__(
        self,
        *,
        context: NeutralCaseContext,
        retriever: HybridRetriever,
        hint_generator: RetrievalHintGenerator,
        extractor: ClinicalFactExtractor,
        reasoner: TemporalReasoner,
        follow_up: EvidenceScopeFollowUp,
    ) -> None:
        self.context = context
        self._retriever = retriever
        self._hint_generator = hint_generator
        self._extractor = extractor
        self._reasoner = reasoner
        self._follow_up = follow_up

    def prepare(self, requirement: AtomicSubRequirement) -> PreparedSubRequirement:
        hints = self._hint_generator.generate(requirement, self.context)
        evidence = self._retriever.retrieve(
            RetrievalQuery(
                context=self.context,
                hints=hints,
                evidence_scope=EvidenceScope.SUBMITTED_PACKET,
                restrict_to_case=True,
            )
        )
        facts = self._extractor.extract(requirement, evidence)
        derived = self._reasoner.derive(facts, requirement.semantics)
        return PreparedSubRequirement(
            context=self.context,
            hints=hints,
            evidence=evidence,
            facts=facts,
            derived=derived,
        )

    def follow_up(self, label, hints: RetrievalHints) -> ScopeFollowUp:
        return self._follow_up.follow_up(
            label,
            RetrievalQuery(
                context=self.context,
                hints=hints,
                evidence_scope=EvidenceScope.SUBMITTED_PACKET,
            ),
        )
