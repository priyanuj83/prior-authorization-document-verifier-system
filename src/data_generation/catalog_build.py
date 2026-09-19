"""Build src/data_generation/catalog.yaml from the Synthea extract."""

from __future__ import annotations

from datetime import date
from typing import List

from .paths import CATALOG_PATH
from .synthea import SyntheaStore, parse_date
from .yamlio import dump_yaml

FROZEN_PATIENTS = {
    "34382e29-6854-4353-85be-802262bfea6e",  # Ethan
    "c2128123-c579-48b9-8452-d1741f5a3c4c",  # Gianna
    "1ab6d5c8-edbe-4c71-8f7a-2af7010af2ab",  # Sharilyn
}

MENISCUS = "Tear of meniscus of knee"
MCL = "Injury of medial collateral ligament of knee"
ACL = "Injury of anterior cruciate ligament"
PATELLAR = "Rupture of patellar tendon"
OA = "Osteoarthritis of knee"
CUFF = "Injury of tendon of the rotator cuff of shoulder"
WHIPLASH = "Whiplash injury to neck"


def _sorted_ids(store: SyntheaStore, description: str) -> List[str]:
    ids = store.patients_with_condition(description)
    ids.sort()
    return ids


def _pt_days(store: SyntheaStore, pid: str, hint: str) -> int:
    best = -1
    for cp in store.pt_careplans(pid):
        reason = (cp.get("REASONDESCRIPTION") or "").lower()
        if hint.lower() in reason or hint == "*":
            d = cp.get("duration_days")
            if d is not None and d > best:
                best = d
    return best


def build_catalog(store: SyntheaStore) -> dict:
    cases = []
    seed = 1

    def add(prefix_counter, prefix, pid, policy, variant, anchor, flags=None, plan_id=None):
        nonlocal seed
        n = prefix_counter[prefix]
        case_id = f"{prefix}-{n:04d}"
        prefix_counter[prefix] = n + 1
        rec = {
            "case_id": case_id,
            "patient_id": pid,
            "policy_id": policy,
            "variant": variant,
            "anchor_condition": anchor,
            "seed": seed,
        }
        if flags:
            rec["flags"] = flags
        if plan_id:
            rec["plan_id"] = plan_id
        cases.append(rec)
        seed += 1
        return case_id

    counters = {
        "KNEE-ARTHRO": 4,  # 0001-0003 frozen
        "KNEE-MRI": 1,
        "TKA": 1,
        "SHOULDER-RCR": 1,
        "SPINE-MRI": 1,
    }

    # --- Arthroscopy: 6 meniscus patients x 3 variants ---
    for pid in _sorted_ids(store, MENISCUS):
        days = _pt_days(store, pid, "meniscus")
        oa = store.has_condition(pid, OA)
        if oa:
            variants = ["full_packet", "omit_pt_notes", "distractor_unrelated"]
        elif days >= 42:
            variants = ["full_packet", "omit_pt_notes", "omit_imaging"]
            if pid == "34382e29-6854-4353-85be-802262bfea6e":
                variants = ["omit_pt_notes", "home_pt_enclosed", "omit_imaging"]
        else:
            variants = ["omit_pt_notes", "short_pt_enclosed", "overclaim_attestation"]
        for v in variants:
            add(counters, "KNEE-ARTHRO", pid, "PA-KNEE-ARTHRO-001", v, MENISCUS)

    # Date-gate: ACL episodes in 2010–2011, forced onto Humana so the 2013-06-01
    # requirement is not yet in force. Notes stay before the request date.
    for pid in _sorted_ids(store, ACL):
        cond = store.first_condition(pid, ACL)
        start = parse_date(cond["START"]) if cond else None
        if start and start < date(2013, 1, 1):
            add(
                counters, "KNEE-MRI", pid, "PA-KNEE-MRI-001",
                "pre_effective_date", ACL, plan_id="HUMANA-COMMERCIAL-01",
            )

    # --- Knee MRI: injury cohorts x 2, plus a few severe-OA exclusions ---
    injury = []
    for desc in (MENISCUS, MCL, ACL, PATELLAR):
        for pid in _sorted_ids(store, desc):
            injury.append((pid, desc))
    # unique patients, first condition wins
    seen = set()
    unique_injury = []
    for pid, desc in injury:
        if pid in seen:
            continue
        seen.add(pid)
        unique_injury.append((pid, desc))

    for pid, desc in unique_injury:
        add(counters, "KNEE-MRI", pid, "PA-KNEE-MRI-001", "full_packet", desc)
        add(counters, "KNEE-MRI", pid, "PA-KNEE-MRI-001", "omit_exam", desc)

    oa_ids = [p for p in _sorted_ids(store, OA) if p not in seen][:4]
    for pid in oa_ids:
        add(counters, "KNEE-MRI", pid, "PA-KNEE-MRI-001", "severe_oa", OA, flags=["omit_exam"])

    # --- TKA: 25 OA patients, 2 variants each ---
    oa_all = _sorted_ids(store, OA)
    # Prefer patients with any PT, then fill.
    with_pt = [p for p in oa_all if store.pt_careplans(p)]
    without = [p for p in oa_all if p not in with_pt]
    tka_pts = (with_pt + without)[:25]
    for i, pid in enumerate(tka_pts):
        if i < 5:
            add(counters, "TKA", pid, "PA-TKA-001", "full_packet", OA)
            add(counters, "TKA", pid, "PA-TKA-001", "omit_pt_notes", OA)
        else:
            add(counters, "TKA", pid, "PA-TKA-001", "omit_pt_notes", OA)
            add(counters, "TKA", pid, "PA-TKA-001", "short_pt_enclosed", OA)

    # --- Shoulder: all 12 x 3 ---
    for pid in _sorted_ids(store, CUFF):
        days = _pt_days(store, pid, "rotator")
        extra_pt = any(
            "ankle" in (c.get("REASONDESCRIPTION") or "").lower()
            or "wrist" in (c.get("REASONDESCRIPTION") or "").lower()
            for c in store.pt_careplans(pid)
        )
        if days >= 42:
            variants = ["full_packet", "omit_imaging", "distractor_unrelated" if extra_pt or True else "omit_pt_notes"]
        else:
            variants = ["omit_pt_notes", "short_pt_enclosed", "omit_imaging"]
        for v in variants:
            add(counters, "SHOULDER-RCR", pid, "PA-SHOULDER-RCR-001", v, CUFF)

    # --- Spine trauma: 15 whiplash x 2 ---
    whip = _sorted_ids(store, WHIPLASH)
    # Prefer insured
    def insured(pid):
        cond = store.first_condition(pid, WHIPLASH)
        enc = store.encounters_by_id.get((cond or {}).get("ENCOUNTER") or "")
        name = store.payer_name((enc or {}).get("PAYER"))
        return name != "NO_INSURANCE"

    whip_sorted = sorted(whip, key=lambda p: (0 if insured(p) else 1, p))[:15]
    for pid in whip_sorted:
        add(counters, "SPINE-MRI", pid, "PA-SPINE-MRI-001", "full_packet", WHIPLASH)
        add(counters, "SPINE-MRI", pid, "PA-SPINE-MRI-001", "omit_imaging", WHIPLASH)

    return {
        "corpus_version": "0.3.0",
        "frozen_case_ids": [
            "KNEE-ARTHRO-0001",
            "KNEE-ARTHRO-0002",
            "KNEE-ARTHRO-0003",
        ],
        "notes": (
            "Generated cases only. Frozen IDs are never overwritten. "
            "Output is always data/cases/<case_id>/."
        ),
        "cases": cases,
    }


def write_catalog(store: SyntheaStore, path=None) -> dict:
    catalog = build_catalog(store)
    path = path or CATALOG_PATH
    dump_yaml(
        path,
        catalog,
        header="# Recipe list for src/data_generation.generate\n# Output: data/cases/<case_id>/",
    )
    return catalog
