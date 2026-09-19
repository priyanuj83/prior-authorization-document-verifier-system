"""Assemble clinical facts and a render plan from Synthea + variant spec."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional

from .episode import Episode, body_region_from_text, requested_region
from .names import (
    ED_AUTHORS,
    PROVIDERS,
    PT_AUTHORS,
    RADIOLOGISTS,
    age_on,
    display_name,
    mrn_for,
    pick,
    strip_synthea_name,
)
from .synthea import SyntheaStore, parse_date
from .variants import VariantSpec


@dataclass
class ClinicalFacts:
    pain: bool = True
    mechanical: bool = True
    locking: bool = True
    kl_grade: int = 1
    oa_present: bool = False
    oa_onset: Optional[date] = None
    mri_tear: bool = True
    bucket_handle: bool = False
    meniscal_root_intact: bool = True
    pt_start: Optional[date] = None
    pt_stop: Optional[date] = None
    pt_days: Optional[int] = None
    pt_modality: str = "in_person"
    pt_body_region: Optional[str] = None
    pt_sessions: int = 12
    pt_response: str = "no_improvement"
    pt_provenance: str = "synthea"
    infection_absent: bool = True
    function_impaired: bool = True
    effusion: bool = True
    acute_injury: bool = True
    exam_abnormal: bool = True
    cuff_tear: bool = True
    trauma: bool = False
    plain_film_inconclusive: bool = False
    cord_suspected: bool = False
    unrelated_pt: list = field(default_factory=list)


@dataclass
class RenderPlan:
    enclose_ed: bool = True
    enclose_ortho: bool = True
    enclose_pt: bool = True
    enclose_mri: bool = False
    enclose_us: bool = False
    enclose_xray_note: bool = False
    enclose_followup: bool = True
    enclose_distractor: bool = False
    overclaim_pt: bool = False


@dataclass
class CaseContext:
    case_id: str
    policy_id: str
    plan_id: str
    seed: int
    variant_name: str
    spec: VariantSpec
    patient_id: str
    first: str
    last: str
    full_name: str
    sex: str
    birthdate: date
    age: int
    city: str
    state: str
    mrn: str
    episode: Episode
    facts: ClinicalFacts
    render: RenderPlan
    provider: tuple
    ed_author: str
    pt_author: str
    radiologist: str
    chart_totals: dict
    service_key: str
    service_description: str
    diagnosis_description: str
    diagnosis_snomed: Optional[str]


def _kl_grade(episode: Episode, spec: VariantSpec) -> int:
    if spec.oa_grade == "severe":
        return 4
    if spec.oa_grade == "mild":
        return 1
    return 4 if episode.oa_present else 1


def _pt_dates(episode: Episode, spec: VariantSpec, region: str):
    provenance = "synthea"
    start = stop = None
    days = None
    body = None
    source_cp = episode.pt

    if spec.pt_duration_source == "authored_long":
        days = spec.authored_pt_days or 100
        stop = episode.request_date - timedelta(days=14)
        start = stop - timedelta(days=days)
        provenance = "authored"
        body = region
    elif spec.pt_duration_source == "authored_short":
        days = spec.authored_pt_days or 30
        if source_cp and source_cp.get("start_date") and source_cp.get("stop_date"):
            start = source_cp["start_date"]
            stop = source_cp["stop_date"]
            days = source_cp.get("duration_days") or days
            provenance = "synthea"
            body = body_region_from_text(source_cp.get("REASONDESCRIPTION")) or region
        else:
            stop = episode.request_date - timedelta(days=7)
            start = stop - timedelta(days=days)
            provenance = "authored"
            body = region
    elif source_cp:
        start = source_cp.get("start_date")
        stop = source_cp.get("stop_date")
        days = source_cp.get("duration_days")
        body = body_region_from_text(source_cp.get("REASONDESCRIPTION")) or region
        provenance = "synthea"
    return start, stop, days, body, provenance


def build_context(
    store: SyntheaStore,
    case_id: str,
    policy_id: str,
    plan_id: str,
    service_key: str,
    episode: Episode,
    spec: VariantSpec,
    seed: int,
    variant_name: str,
) -> CaseContext:
    rec = store.patient(episode.patient_id)
    first, last = strip_synthea_name(rec.get("FIRST", ""), rec.get("LAST", ""))
    birth = parse_date(rec["BIRTHDATE"])
    region = requested_region(policy_id)
    pt_start, pt_stop, pt_days, pt_body, pt_prov = _pt_dates(episode, spec, region)
    sessions = 8
    if pt_days:
        sessions = max(4, min(20, int(round(pt_days / 3.5))))

    facts = ClinicalFacts(
        pain=True,
        mechanical=spec.mechanical_symptoms,
        locking=spec.locking and spec.mechanical_symptoms,
        kl_grade=_kl_grade(episode, spec),
        oa_present=episode.oa_present,
        oa_onset=episode.oa_onset,
        mri_tear=policy_id != "PA-SHOULDER-RCR-001",
        bucket_handle=False,
        pt_start=pt_start,
        pt_stop=pt_stop,
        pt_days=pt_days,
        pt_modality=spec.pt_modality,
        pt_body_region=pt_body or region,
        pt_sessions=sessions,
        pt_provenance=pt_prov,
        infection_absent=spec.document_infection_absent,
        function_impaired=spec.function_impaired,
        effusion=spec.document_effusion,
        acute_injury=True,
        exam_abnormal=spec.document_exam,
        cuff_tear=spec.cuff_tear_present,
        trauma=policy_id == "PA-SPINE-MRI-001",
        plain_film_inconclusive=spec.trauma_plain_film_inconclusive,
        cord_suspected=spec.suspect_cord_injury,
        unrelated_pt=episode.unrelated_pt,
    )

    render = RenderPlan(
        enclose_pt=spec.enclose_pt and pt_start is not None,
        enclose_mri=spec.enclose_advanced_imaging and policy_id in (
            "PA-KNEE-ARTHRO-001",
            "PA-SHOULDER-RCR-001",
        ),
        enclose_xray_note=spec.enclose_xray and policy_id == "PA-SPINE-MRI-001",
        enclose_distractor=spec.enclose_distractor,
        overclaim_pt=spec.overclaim_pt,
        enclose_ortho=policy_id != "PA-SPINE-MRI-001",
        enclose_followup=True,
        enclose_ed=True,
    )
    if policy_id == "PA-KNEE-MRI-001":
        render.enclose_mri = False
        render.enclose_pt = spec.enclose_pt and pt_start is not None and spec.name != "full_packet"
        # B2 READY path does not need PT notes.
        if spec.name.startswith("full_packet"):
            render.enclose_pt = False
        if spec.pt_duration_source in ("authored_short",) or spec.name.startswith("short_pt"):
            render.enclose_pt = True

    services = {
        "PA-KNEE-ARTHRO-001": (
            "Arthroscopic partial meniscectomy, {side} knee",
            episode.anchor_condition,
        ),
        "PA-KNEE-MRI-001": (
            "MRI of the {side} knee, without contrast",
            episode.anchor_condition,
        ),
        "PA-TKA-001": (
            "Total knee arthroplasty, {side}",
            "Osteoarthritis of knee",
        ),
        "PA-SHOULDER-RCR-001": (
            "Rotator cuff repair, {side} shoulder",
            episode.anchor_condition,
        ),
        "PA-SPINE-MRI-001": (
            "MRI of the cervical spine without contrast",
            episode.anchor_condition,
        ),
    }
    desc_t, dx = services[policy_id]
    side = episode.laterality

    return CaseContext(
        case_id=case_id,
        policy_id=policy_id,
        plan_id=plan_id,
        seed=seed,
        variant_name=variant_name,
        spec=spec,
        patient_id=episode.patient_id,
        first=first,
        last=last,
        full_name=display_name(rec.get("FIRST", ""), rec.get("LAST", "")),
        sex=rec.get("GENDER", "U"),
        birthdate=birth,
        age=age_on(birth, episode.request_date),
        city=rec.get("CITY", ""),
        state=rec.get("STATE", ""),
        mrn=mrn_for(episode.patient_id),
        episode=episode,
        facts=facts,
        render=render,
        provider=pick(seed, PROVIDERS),
        ed_author=pick(seed + 1, ED_AUTHORS),
        pt_author=pick(seed + 2, PT_AUTHORS),
        radiologist=pick(seed + 3, RADIOLOGISTS),
        chart_totals=store.chart_totals(episode.patient_id),
        service_key=service_key,
        service_description=desc_t.format(side=side),
        diagnosis_description=dx,
        diagnosis_snomed=episode.anchor_code,
    )
