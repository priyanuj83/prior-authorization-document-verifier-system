from datetime import date

from src.case_loading.models import (
    Attestation,
    ClinicalNote,
    Member,
    PriorAuthorizationRequest,
    RecordsScope,
    RequestedService,
)
from src.enums import AtomicLabel, EvidenceScope, RetrievalChannel
from src.indexing.embeddings.protocol import EmbeddingProvider
from src.indexing.index_writer.memory import IndexedChunk, InMemoryClinicalIndex
from src.indexing.pipeline import index_clinical_notes
from src.requirement_models.models import AtomicSubRequirement
from src.requirement_models.semantics import PolicySemantics
from src.retrieval.deduplication import merge_and_deduplicate
from src.retrieval.hint_generation import (
    PlaceholderRetrievalHintGenerator,
    build_neutral_case_context,
)
from src.retrieval.hybrid_search import HybridRetriever
from src.retrieval.query_models import (
    EvidenceCandidate,
    NeutralCaseContext,
    RetrievalHints,
    RetrievalQuery,
    RetrievalSignals,
)
from src.retrieval.reranking import PassthroughReranker
from src.retrieval.scope_follow_up import EvidenceScopeFollowUp


def _request() -> PriorAuthorizationRequest:
    return PriorAuthorizationRequest(
        submitted_date=date(2014, 4, 16),
        member=Member(
            name="Ethan Goyette",
            member_id="SYN-34382E29",
            dob=None,
            sex=None,
            plan=None,
            plan_id="HUMANA-COMMERCIAL-01",
        ),
        requested_service=RequestedService(
            description="Arthroscopic partial meniscectomy, right knee",
            service_key="knee_arthroscopy",
            laterality="right",
        ),
        attestations=(
            Attestation(
                id="AT3",
                text="The patient completed 6 weeks of physical therapy.",
            ),
        ),
        records_scope=RecordsScope(
            episode_start=date(2014, 1, 31),
            episode_end=date(2014, 4, 16),
        ),
    )


def _requirement() -> AtomicSubRequirement:
    return AtomicSubRequirement(
        criterion_id="C4",
        sub_requirement_id="C4.4",
        text="PT duration >= 6 weeks",
        semantics=PolicySemantics(
            required_facts=("PT start", "PT continuation"),
            supporting_patterns=("documented PT start",),
            refuting_conditions=("PT declined", "documented duration below threshold"),
            lookback_days=365,
        ),
    )


def _context() -> NeutralCaseContext:
    return build_neutral_case_context("CASE-1", _request())


def _signals(lexical: float = 0.0) -> RetrievalSignals:
    return RetrievalSignals(
        semantic_similarity=0.0,
        lexical_match=lexical,
        body_part_match=None,
        laterality_match=None,
        note_type_match=None,
        support_pattern_match=None,
        contradiction_pattern_match=None,
    )


def _candidate(chunk_id: str, score: float, channel: RetrievalChannel) -> EvidenceCandidate:
    return EvidenceCandidate(
        note_id=chunk_id,
        chunk_id=chunk_id,
        source_file=f"{chunk_id}.md",
        section="HPI",
        note_date=date(2014, 1, 10),
        evidence_scope=EvidenceScope.SUBMITTED_PACKET,
        text="text",
        retrieval_score=score,
        retrieval_signals=_signals(score),
        channels=(channel,),
        case_id="CASE-1",
        patient_id="SYN-34382E29",
    )


def test_neutral_context_and_hints_exclude_attestations() -> None:
    context = _context()
    assert not hasattr(context, "attestations")
    hints = PlaceholderRetrievalHintGenerator().generate(_requirement(), context)
    blob = " ".join(
        [
            hints.concept,
            " ".join(hints.relevant_concepts),
            " ".join(hints.supporting_patterns),
            " ".join(hints.contradictory_patterns),
        ]
    )
    assert "completed 6 weeks of physical therapy" not in blob
    assert hints.body_part == "knee"
    assert hints.laterality == "right"
    assert hints.relevant_date_range.start == date(2013, 4, 16)
    assert hints.relevant_date_range.end == date(2014, 4, 16)
    assert hints.hard_date_filter is False
    assert "PT declined" in hints.contradictory_patterns


def test_merge_keeps_a_chunk_once_when_it_hits_both_channels() -> None:
    support = (_candidate("A", 0.2, RetrievalChannel.SUPPORT),)
    contradiction = (_candidate("A", 0.9, RetrievalChannel.CONTRADICTION),)
    merged = merge_and_deduplicate(support, contradiction)
    assert len(merged) == 1
    assert merged[0].channels == (RetrievalChannel.SUPPORT, RetrievalChannel.CONTRADICTION)
    assert merged[0].retrieval_score == 0.9
    assert merged[0].support_signals is not None
    assert merged[0].contradiction_signals is not None


def test_hard_filters_keep_unknown_laterality_and_drop_other_patients() -> None:
    index = InMemoryClinicalIndex()
    shared = dict(
        note_type="orthopedic note",
        section="HPI",
        body_part=None,
        text="Patient continues physical therapy.",
        embedding=(),
    )
    index.add(
        IndexedChunk(
            chunk_id="match",
            note_id="N1",
            case_id="CASE-1",
            patient_id="SYN-34382E29",
            source_file="input/notes/match.md",
            note_date=date(2014, 2, 1),
            laterality=None,
            evidence_scope=EvidenceScope.SUBMITTED_PACKET,
            **shared,
        )
    )
    index.add(
        IndexedChunk(
            chunk_id="wrong-side",
            note_id="N2",
            case_id="CASE-1",
            patient_id="SYN-34382E29",
            source_file="input/notes/wrong-side.md",
            note_date=date(2014, 2, 2),
            laterality="left",
            evidence_scope=EvidenceScope.SUBMITTED_PACKET,
            **shared,
        )
    )
    index.add(
        IndexedChunk(
            chunk_id="other-patient",
            note_id="N3",
            case_id="CASE-9",
            patient_id="OTHER",
            source_file="input/notes/other.md",
            note_date=date(2014, 2, 2),
            laterality="right",
            evidence_scope=EvidenceScope.SUBMITTED_PACKET,
            **shared,
        )
    )
    index.add(
        IndexedChunk(
            chunk_id="ehr",
            note_id="N4",
            case_id="CASE-1",
            patient_id="SYN-34382E29",
            source_file="ehr/outside.md",
            note_date=date(2014, 2, 2),
            laterality="right",
            evidence_scope=EvidenceScope.AVAILABLE_EHR,
            **shared,
        )
    )
    hints = PlaceholderRetrievalHintGenerator().generate(_requirement(), _context())
    result = HybridRetriever(index).retrieve(
        RetrievalQuery(
            context=_context(),
            hints=hints,
            evidence_scope=EvidenceScope.SUBMITTED_PACKET,
        )
    )
    ids = {item.chunk_id for item in result.merged_candidates}
    assert ids == {"match", "wrong-side"}
    unknown = next(item for item in result.merged_candidates if item.chunk_id == "match")
    mismatch = next(item for item in result.merged_candidates if item.chunk_id == "wrong-side")
    assert unknown.retrieval_signals.laterality_match is None
    assert mismatch.retrieval_signals.laterality_match is False


def test_hard_date_filter_drops_dated_notes_outside_the_window_only() -> None:
    index = InMemoryClinicalIndex()
    for chunk_id, note_date in (("inside", date(2014, 3, 1)), ("outside", date(2013, 1, 1)), ("undated", None)):
        index.add(
            IndexedChunk(
                chunk_id=chunk_id,
                note_id=chunk_id,
                case_id="CASE-1",
                patient_id="SYN-34382E29",
                source_file=f"{chunk_id}.md",
                note_date=note_date,
                note_type=None,
                section="document",
                body_part=None,
                laterality=None,
                evidence_scope=EvidenceScope.SUBMITTED_PACKET,
                text="physical therapy",
                embedding=(),
            )
        )
    hints = RetrievalHints(
        concept="physical therapy",
        relevant_date_range=PlaceholderRetrievalHintGenerator()
        .generate(_requirement(), _context())
        .relevant_date_range,
        hard_date_filter=True,
    )
    result = HybridRetriever(index).retrieve(
        RetrievalQuery(context=_context(), hints=hints, evidence_scope=EvidenceScope.SUBMITTED_PACKET)
    )
    assert {item.chunk_id for item in result.merged_candidates} == {"inside", "undated"}


def test_lexical_channel_prefers_exact_clinical_terms() -> None:
    notes = [
        ClinicalNote(
            file="pt.md",
            path="input/notes/pt.md",
            content="**Plan**\n\nPatient declined physical therapy after three weeks.",
        ),
        ClinicalNote(
            file="other.md",
            path="input/notes/other.md",
            content="**Plan**\n\nWound check completed.",
        ),
    ]
    index = index_clinical_notes(
        notes,
        case_id="CASE-1",
        patient_id="SYN-34382E29",
        evidence_scope=EvidenceScope.SUBMITTED_PACKET,
    )
    hints = PlaceholderRetrievalHintGenerator().generate(_requirement(), _context())
    result = HybridRetriever(index).retrieve(
        RetrievalQuery(context=_context(), hints=hints, evidence_scope=EvidenceScope.SUBMITTED_PACKET)
    )
    contradiction = result.contradiction_candidates
    assert contradiction[0].source_file == "input/notes/pt.md"
    assert contradiction[0].retrieval_signals.contradiction_pattern_match is True
    assert contradiction[1].retrieval_signals.contradiction_pattern_match is False


def test_vector_similarity_is_only_a_signal() -> None:
    class FixedEmbedder:
        def embed(self, text: str):
            if "therapist-guided" in text or "supervised" in text:
                return (1.0, 0.0)
            return (0.0, 1.0)

    embedder: EmbeddingProvider = FixedEmbedder()
    note = ClinicalNote(
        file="rehab.md",
        path="input/notes/rehab.md",
        content="Patient participated in therapist-guided strengthening exercises.",
    )
    index = index_clinical_notes(
        [note],
        case_id="CASE-1",
        patient_id="SYN-34382E29",
        evidence_scope=EvidenceScope.SUBMITTED_PACKET,
        embedder=embedder,
    )
    hints = RetrievalHints(concept="PT was supervised")
    result = HybridRetriever(index, embedder=embedder).retrieve(
        RetrievalQuery(context=_context(), hints=hints, evidence_scope=EvidenceScope.SUBMITTED_PACKET)
    )
    assert result.merged_candidates[0].retrieval_signals.semantic_similarity > 0.0
    assert result.merged_candidates[0].retrieval_score > 0.0


def test_passthrough_reranker_can_limit_without_dropping_by_default() -> None:
    candidates = (
        _candidate("low", 0.1, RetrievalChannel.SUPPORT),
        _candidate("high", 0.8, RetrievalChannel.SUPPORT),
    )
    assert [item.chunk_id for item in PassthroughReranker().rerank(candidates)] == ["high", "low"]
    assert [item.chunk_id for item in PassthroughReranker(candidate_limit=1).rerank(candidates)] == ["high"]


def test_not_proven_ehr_suggestion_does_not_search_on_refuted() -> None:
    index = InMemoryClinicalIndex()
    index.add(
        IndexedChunk(
            chunk_id="ehr-pt",
            note_id="E1",
            case_id="OTHER-CASE",
            patient_id="SYN-34382E29",
            source_file="ehr/pt.md",
            note_date=date(2014, 3, 1),
            note_type="physical therapy note",
            section="document",
            body_part="knee",
            laterality="right",
            evidence_scope=EvidenceScope.AVAILABLE_EHR,
            text="Documented PT start for the right knee.",
            embedding=(),
        )
    )
    hints = PlaceholderRetrievalHintGenerator().generate(_requirement(), _context())
    query = RetrievalQuery(
        context=_context(),
        hints=hints,
        evidence_scope=EvidenceScope.SUBMITTED_PACKET,
    )
    follow = EvidenceScopeFollowUp(HybridRetriever(index)).follow_up(AtomicLabel.NOT_PROVEN, query)
    assert follow.submitted_label is AtomicLabel.NOT_PROVEN
    assert follow.ehr_support_suggestions
    assert "PROVEN" in follow.message
    assert follow.ehr_support_suggestions[0].evidence_scope is EvidenceScope.AVAILABLE_EHR

    class ExplodingRetriever:
        def retrieve(self, retrieval_query):
            raise AssertionError("REFUTED must not search the EHR")

    refuted = EvidenceScopeFollowUp(ExplodingRetriever()).follow_up(AtomicLabel.REFUTED, query)
    assert refuted.ehr_support_suggestions == ()
    assert refuted.ehr_contradiction_flags == ()
