"""Write data/generation/splits.yaml — split by patient, never by case."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path

from . import FROZEN_CASE_IDS
from .paths import CASES_DIR, SPLITS_PATH
from .yamlio import dump_yaml, load_yaml


def patient_split(patient_id: str) -> str:
    h = int(hashlib.md5(patient_id.encode()).hexdigest(), 16)
    return "eval" if h % 5 == 0 else "train"


def build_splits(cases_dir: Path = None) -> dict:
    cases_dir = cases_dir or CASES_DIR
    by_patient = defaultdict(list)
    rows = []
    for d in sorted(cases_dir.iterdir()):
        ledger = d / "gold" / "ledger.yaml"
        if not ledger.exists():
            continue
        doc = load_yaml(ledger)
        pid = (doc.get("patient") or {}).get("synthea_patient_id")
        if not pid:
            continue
        origin = "hand-authored" if d.name in FROZEN_CASE_IDS else "generated"
        rec = {"case_id": d.name, "patient_id": pid, "origin": origin}
        by_patient[pid].append(rec)
        rows.append(rec)

    # Frozen patients always eval, and all their generated variants follow.
    frozen_pids = set()
    for rec in rows:
        if rec["origin"] == "hand-authored":
            frozen_pids.add(rec["patient_id"])

    splits = {"train": [], "eval": []}
    assigned = {}
    for pid, recs in by_patient.items():
        bucket = "eval" if pid in frozen_pids else patient_split(pid)
        assigned[pid] = bucket
        for rec in recs:
            rec["split"] = bucket
            splits[bucket].append(rec["case_id"])

    return {
        "rule": "All cases of one patient_id share a split. Frozen seed patients are always eval.",
        "counts": {
            "train_cases": len(splits["train"]),
            "eval_cases": len(splits["eval"]),
            "train_patients": sum(1 for v in assigned.values() if v == "train"),
            "eval_patients": sum(1 for v in assigned.values() if v == "eval"),
        },
        "train": sorted(splits["train"]),
        "eval": sorted(splits["eval"]),
    }


def write_splits(cases_dir: Path = None) -> dict:
    doc = build_splits(cases_dir)
    SPLITS_PATH.parent.mkdir(parents=True, exist_ok=True)
    dump_yaml(SPLITS_PATH, doc, header="# Patient-grouped splits. Never split variants of one patient across train/eval.")
    return doc
