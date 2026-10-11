from datetime import date

from src.atomic_verification.decision import label_from_structured_evidence
from src.clinical_extraction.event_models import ClinicalEvent, StructuredClinicalFacts
from src.enums import AtomicLabel, EvidenceState
from src.reasoning import TemporalReasoner
from src.requirement_models.semantics import PolicySemantics


def _event(**kwargs) -> ClinicalEvent:
    defaults = dict(
        source_file="note.md",
        evidence="source",
        extraction_rationale="explicit",
        evidence_state=EvidenceState.EXPLICIT,
    )
    defaults.update(kwargs)
    return ClinicalEvent(**defaults)


def test_elapsed_duration_is_not_treated_as_continuous_without_a_rule() -> None:
    facts = StructuredClinicalFacts(
        events=(
            _event(event_date=date(2014, 1, 1), event_type="pt_start"),
            _event(event_date=date(2014, 2, 20), event_type="pt_resume", gap_duration_days=35),
        )
    )
    derived = TemporalReasoner().derive(
        facts,
        PolicySemantics(threshold_days=42, threshold_comparator=">=", continuity_required=False),
    )
    assert derived.elapsed_days == 50
    assert 35 in derived.gap_days
    assert derived.continuity_met is None
    assert derived.continuous_duration_days is None
    assert derived.threshold_met is True


def test_continuity_rule_breaks_a_long_gap_and_missing_rule_does_not_fail_it() -> None:
    facts = StructuredClinicalFacts(
        events=(
            _event(event_date=date(2014, 1, 1), event_type="pt_start"),
            _event(event_date=date(2014, 2, 20), event_type="pt_resume"),
        )
    )
    with_rule = TemporalReasoner().derive(
        facts,
        PolicySemantics(
            threshold_days=42,
            continuity_required=True,
            continuity_max_gap_days=14,
        ),
    )
    assert with_rule.continuity_met is False
    assert with_rule.continuous_duration_days == 0
    assert with_rule.threshold_met is False

    without_rule = TemporalReasoner().derive(
        facts,
        PolicySemantics(threshold_days=42, continuity_required=True),
    )
    assert without_rule.continuity_met is None
    assert without_rule.threshold_met is None
    assert "no continuity rule" in without_rule.rationale


def test_not_mentioned_events_are_not_used_as_dates() -> None:
    facts = StructuredClinicalFacts(
        events=(
            _event(
                evidence_state=EvidenceState.NOT_MENTIONED,
                event_date=date(2014, 1, 1),
            ),
            _event(
                evidence_state=EvidenceState.NOT_MENTIONED,
                event_date=date(2014, 4, 1),
            ),
        )
    )
    derived = TemporalReasoner().derive(facts, PolicySemantics(threshold_days=42))
    assert derived.elapsed_days is None
    assert derived.threshold_met is None


def test_explicit_conflict_is_refuted_and_similarity_is_not_consulted() -> None:
    facts = StructuredClinicalFacts(
        events=(
            _event(
                evidence="Patient declined physical therapy.",
                conflicts_with_requirement=True,
            ),
            _event(
                evidence_state=EvidenceState.NOT_MENTIONED,
                conflicts_with_requirement=True,
            ),
        )
    )
    derived = TemporalReasoner().derive(facts, PolicySemantics())
    label, _rationale = label_from_structured_evidence(facts, derived)
    assert label is AtomicLabel.REFUTED


def test_explicit_threshold_is_proven_and_missing_facts_are_not_proven() -> None:
    facts = StructuredClinicalFacts(
        events=(
            _event(event_date=date(2014, 1, 10), evidence="Initial PT evaluation."),
            _event(event_date=date(2014, 2, 28), evidence="Patient continues PT."),
        )
    )
    semantics = PolicySemantics(threshold_days=42, threshold_comparator=">=")
    derived = TemporalReasoner().derive(facts, semantics)
    label, _rationale = label_from_structured_evidence(facts, derived)
    assert derived.elapsed_days == 49
    assert label is AtomicLabel.PROVEN

    empty = TemporalReasoner().derive(StructuredClinicalFacts(events=()), semantics)
    missing, rationale = label_from_structured_evidence(StructuredClinicalFacts(events=()), empty)
    assert missing is AtomicLabel.NOT_PROVEN
    assert "not proof" in rationale
