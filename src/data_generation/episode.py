"""Pick an episode window from a Synthea chart for one anchor condition."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional

from .names import laterality_for
from .synthea import SyntheaStore, parse_date


BODY_HINTS = {
    "knee": ("knee", "meniscus", "cruciate", "collateral", "patellar"),
    "shoulder": ("shoulder", "rotator cuff", "cuff"),
    "neck": ("whiplash", "neck", "cervical"),
    "ankle": ("ankle",),
    "wrist": ("wrist",),
}


def body_region_from_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    low = text.lower()
    for region, hints in BODY_HINTS.items():
        if any(h in low for h in hints):
            return region
    return None


def requested_region(policy_id: str) -> str:
    if policy_id == "PA-SHOULDER-RCR-001":
        return "shoulder"
    if policy_id == "PA-SPINE-MRI-001":
        return "neck"
    return "knee"


@dataclass
class Episode:
    patient_id: str
    anchor_condition: str
    anchor_code: Optional[str]
    index_date: date
    request_date: date
    laterality: str
    encounter_id: Optional[str]
    encounter_class: Optional[str]
    payer_id: Optional[str]
    payer_name: str
    pt: Optional[dict]
    unrelated_pt: List[dict] = field(default_factory=list)
    oa_onset: Optional[date] = None
    oa_present: bool = False


def _match_pt(careplans, region: str, index: date) -> Optional[dict]:
    candidates = []
    for cp in careplans:
        if not cp.get("is_pt"):
            continue
        reason_region = body_region_from_text(cp.get("REASONDESCRIPTION"))
        if reason_region != region:
            continue
        start = cp.get("start_date")
        if start is None:
            continue
        # Prefer PT starting at or shortly after index.
        delta = abs((start - index).days)
        candidates.append((delta, start, cp))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][2]


def build_episode(
    store: SyntheaStore,
    patient_id: str,
    anchor_condition: str,
    policy_id: str,
    pre_effective: bool = False,
    effective_from: Optional[date] = None,
) -> Episode:
    region = requested_region(policy_id)
    cond = store.first_condition(patient_id, anchor_condition)
    if cond is None:
        raise ValueError(f"{patient_id} has no condition {anchor_condition}")

    index = parse_date(cond["START"])
    enc = store.encounters_by_id.get(cond.get("ENCOUNTER") or "")
    payer_id = enc.get("PAYER") if enc else None
    payer_name = store.payer_name(payer_id)

    oa = store.first_condition(patient_id, "Osteoarthritis of knee")
    oa_onset = parse_date(oa["START"]) if oa else None

    pt = _match_pt(store.careplans_for(patient_id), region, index)
    unrelated = []
    for cp in store.pt_careplans(patient_id):
        if pt is not None and cp.get("Id") == pt.get("Id"):
            continue
        unrelated.append(cp)

    if policy_id == "PA-TKA-001":
        # Request sits in the later chart, not at 1970s OA onset.
        late = []
        for e in store.encounters_for(patient_id):
            d = parse_date(e.get("START"))
            if d and d.year >= 2010 and d.year <= 2019:
                late.append((d, e))
        if late:
            late.sort(key=lambda item: item[0])
            request = late[-1][0]
            if enc is None:
                enc = late[-1][1]
                payer_id = enc.get("PAYER")
                payer_name = store.payer_name(payer_id)
        else:
            request = date(2016, 6, 1)
        if pt and pt.get("stop_date"):
            request = max(request, pt["stop_date"] + timedelta(days=14))
    elif pt and pt.get("stop_date"):
        request = pt["stop_date"] + timedelta(days=15)
    elif policy_id == "PA-SPINE-MRI-001":
        request = index + timedelta(days=3)
    else:
        request = index + timedelta(days=21)

    if pre_effective and effective_from:
        request = effective_from - timedelta(days=10)
        if request <= index:
            request = effective_from - timedelta(days=1)

    laterality = laterality_for(patient_id, region)
    return Episode(
        patient_id=patient_id,
        anchor_condition=anchor_condition,
        anchor_code=cond.get("CODE"),
        index_date=index,
        request_date=request,
        laterality=laterality,
        encounter_id=cond.get("ENCOUNTER"),
        encounter_class=(enc or {}).get("ENCOUNTERCLASS"),
        payer_id=payer_id,
        payer_name=payer_name,
        pt=pt,
        unrelated_pt=unrelated,
        oa_onset=oa_onset,
        oa_present=oa is not None,
    )
