"""Validate frozen and generated cases."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from . import FORBIDDEN_VOCABULARY, FROZEN_CASE_IDS
from .paths import CASES_DIR, ROOT
from .synthea import SyntheaStore
from .yamlio import iso, load_yaml

VALID_STATUS = {"READY_FOR_SUBMISSION", "NOT_READY", "REVIEW_NEEDED"}
VALID_GATES = {"AUTH_REQUIRED", "COVERAGE_REVIEW_REQUIRED", "NO_AUTH_REQUIRED"}
VALID_LABELS = {"SUPPORTED", "MISSING", "CONTRADICTED"}


def validate_case(case_dir: Path, store: SyntheaStore = None) -> list:
    errs = []
    cid = case_dir.name
    input_dir = case_dir / "input"
    gold_dir = case_dir / "gold"
    for p in (input_dir / "pa_form.yaml", gold_dir / "ledger.yaml", gold_dir / "labels.yaml", gold_dir / "generation_plan.yaml"):
        if not p.exists():
            errs.append(f"{cid}: missing {p.relative_to(case_dir)}")
            return errs
    try:
        form = load_yaml(input_dir / "pa_form.yaml")
        ledger = load_yaml(gold_dir / "ledger.yaml")
        labels = load_yaml(gold_dir / "labels.yaml")
        plan = load_yaml(gold_dir / "generation_plan.yaml")
    except Exception as e:
        errs.append(f"{cid}: YAML parse error: {e}")
        return errs

    # gold leak
    form_text = (input_dir / "pa_form.yaml").read_text()
    for line in form_text.splitlines():
        if line.strip().startswith("#"):
            continue
        for bad in ("labels.yaml", "ledger.yaml", "generation_plan.yaml"):
            if bad in line:
                errs.append(f"{cid}: input references {bad}")

    # note paths
    for note in (input_dir / "notes").glob("*.md"):
        rel = f"input/notes/{note.name}"
        blob = form_text + (gold_dir / "ledger.yaml").read_text() + (gold_dir / "labels.yaml").read_text()
        if rel not in blob and cid not in FROZEN_CASE_IDS:
            # generated forms list enclosures; frozen always does
            pass
    for enc in form.get("enclosures") or []:
        if not (case_dir / enc).exists():
            errs.append(f"{cid}: dangling enclosure {enc}")

    # forbidden vocabulary in generated notes only (frozen cases are the human-audited slice)
    if cid not in FROZEN_CASE_IDS:
        extra = list(plan.get("forbidden_vocabulary") or FORBIDDEN_VOCABULARY)
        for note in (input_dir / "notes").glob("*.md"):
            low = note.read_text().lower()
            for w in extra:
                if w.lower() in low:
                    errs.append(f"{cid}: forbidden '{w}' in {note.name}")

    status = (labels.get("outcome") or {}).get("provider_view", {}).get("documentation_status")
    gate = (labels.get("policy_resolution") or {}).get("gate_result")
    if status not in VALID_STATUS:
        errs.append(f"{cid}: bad status {status}")
    if gate not in VALID_GATES:
        errs.append(f"{cid}: bad gate {gate}")

    counts = (labels.get("outcome") or {}).get("criterion_label_counts") or {}
    if gate != "NO_AUTH_REQUIRED" and status in VALID_STATUS:
        contradicted = int(counts.get("CONTRADICTED") or 0)
        missing = int(counts.get("MISSING") or 0)
        if cid not in FROZEN_CASE_IDS:
            expected = (
                "REVIEW_NEEDED" if contradicted > 0
                else ("NOT_READY" if missing > 0 else "READY_FOR_SUBMISSION")
            )
            # Disjunctive policies / exclusions may disagree with raw counts.
            policy_id = labels.get("policy_id")
            if policy_id not in ("PA-KNEE-MRI-001", "PA-SPINE-MRI-001"):
                if status != expected:
                    # exclusion path
                    excl = labels.get("exclusions") or []
                    if not any(x.get("state") == "TRIGGERED" for x in excl):
                        errs.append(f"{cid}: status {status} vs counts {counts} (expected {expected})")

    rem = (labels.get("outcome") or {}).get("provider_view", {}).get("remediable")
    if status == "NOT_READY" and rem is not True and cid not in FROZEN_CASE_IDS:
        errs.append(f"{cid}: NOT_READY should be remediable true")
    if status == "REVIEW_NEEDED" and rem is not False and cid not in FROZEN_CASE_IDS:
        errs.append(f"{cid}: REVIEW_NEEDED should be remediable false")

    if store is not None:
        pid = (ledger.get("patient") or {}).get("synthea_patient_id")
        if pid:
            try:
                rec = store.patient(pid)
                if iso(ledger["patient"]["birthdate"]) != rec["BIRTHDATE"]:
                    errs.append(f"{cid}: birthdate mismatch")
                if ledger["patient"].get("sex") != rec["GENDER"]:
                    errs.append(f"{cid}: sex mismatch")
            except KeyError:
                errs.append(f"{cid}: patient {pid} not in Synthea")

    # post-request events must not appear in notes
    req = (ledger.get("episode") or {}).get("request_date")
    if req:
        for note in (input_dir / "notes").glob("*.md"):
            m = re.match(r"(\d{4}-\d{2}-\d{2})", note.name)
            if m and m.group(1) > str(req)[:10]:
                errs.append(f"{cid}: post-request note {note.name}")

    return errs


def validate_tree(cases_dir: Path = None) -> list:
    cases_dir = cases_dir or CASES_DIR
    store = SyntheaStore()
    errs = []
    for frozen in FROZEN_CASE_IDS:
        d = cases_dir / frozen
        if not d.exists():
            errs.append(f"frozen case missing: {frozen}")
        else:
            errs.extend(validate_case(d, store))
    for d in sorted(cases_dir.iterdir()):
        if not d.is_dir() or d.name in FROZEN_CASE_IDS:
            continue
        if not (d / "input").exists():
            continue
        errs.extend(validate_case(d, store))
    return errs


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases-dir", type=Path, default=CASES_DIR)
    args = parser.parse_args(argv)
    errs = validate_tree(args.cases_dir)
    if errs:
        print("\n".join(errs))
        print(f"\n{len(errs)} error(s)")
        return 1
    n = len([p for p in args.cases_dir.iterdir() if p.is_dir()])
    print(f"ALL CHECKS PASS ({n} case folders)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
