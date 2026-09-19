"""Generate case folders under data/cases/ from catalog.yaml."""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

from . import FROZEN_CASE_IDS, GENERATOR_ID
from .catalog_build import write_catalog
from .context import build_context
from .episode import build_episode
from .gold import build_generation_plan, build_labels
from .labels import evaluate, exclusion_triggered, project_outcome
from .ledger import attach_scope, build_ledger
from .paths import CATALOG_PATH, CASES_DIR, ROOT
from .render_form import render_form
from .render_notes import render_notes
from .resolve import SERVICE_KEYS, load_plan, plan_id_for_payer, resolve
from .synthea import SyntheaStore, parse_date
from .variants import apply_policy_defaults, resolve_spec
from .yamlio import dump_yaml, iso, load_yaml


def _scope_lists(store: SyntheaStore, ctx) -> tuple:
    ep = ctx.episode
    excluded = []
    post = []
    for cond in store.conditions_for(ctx.patient_id):
        d = parse_date(cond["START"])
        if d is None:
            continue
        desc = cond["DESCRIPTION"]
        if desc == ep.anchor_condition:
            continue
        if desc == "Osteoarthritis of knee" and ctx.policy_id in ("PA-KNEE-ARTHRO-001", "PA-TKA-001"):
            continue
        in_lb = d <= ep.request_date and (ep.request_date - d).days <= 365
        rec = {
            "date": iso(d),
            "description": desc,
            "in_therapy_lookback": in_lb,
        }
        if d > ep.request_date:
            post.append({"date": iso(d), "description": desc})
        else:
            rec["reason"] = "clinically unrelated to this episode"
            excluded.append(rec)
    return excluded[:12], post[:12]


def generate_one(store: SyntheaStore, entry: dict, out_root: Path) -> dict:
    case_id = entry["case_id"]
    if case_id in FROZEN_CASE_IDS:
        raise RuntimeError(f"Refusing to overwrite frozen case {case_id}")

    policy_id = entry["policy_id"]
    service_key = SERVICE_KEYS[policy_id]
    spec = apply_policy_defaults(
        resolve_spec(entry["variant"], entry.get("flags") or []),
        policy_id,
    )
    # Effective-from for pre_effective variant
    patient = store.patient(entry["patient_id"])
    # Temporary episode without pre_effective to get payer
    tmp = build_episode(store, entry["patient_id"], entry["anchor_condition"], policy_id, pre_effective=False)
    plan_id = entry.get("plan_id") or plan_id_for_payer(tmp.payer_name, entry["patient_id"])
    plan = load_plan(plan_id)
    match = next(x for x in plan["requirements"] if x.get("service_key") == service_key)
    effective = parse_date(match.get("effective_from") or plan.get("effective_from"))

    episode = build_episode(
        store,
        entry["patient_id"],
        entry["anchor_condition"],
        policy_id,
        pre_effective=spec.pre_effective_date,
        effective_from=effective,
    )
    # Old Synthea events can pre-date a plan's auth requirement. That is a
    # deliberate trap only for the pre_effective_date variant.
    if (
        not spec.pre_effective_date
        and effective
        and episode.request_date < effective
    ):
        episode.request_date = max(episode.request_date, effective + timedelta(days=40))
        if episode.request_date <= episode.index_date:
            episode.request_date = episode.index_date + timedelta(days=21)
    ctx = build_context(
        store,
        case_id=case_id,
        policy_id=policy_id,
        plan_id=plan_id,
        service_key=service_key,
        episode=episode,
        spec=spec,
        seed=int(entry.get("seed") or 1),
        variant_name=entry["variant"],
    )
    resolution = resolve(plan_id, service_key, episode.request_date)
    results = evaluate(ctx)
    excl = exclusion_triggered(ctx)
    outcome = project_outcome(ctx, results, resolution["gate_result"], excl)

    notes = render_notes(ctx)
    note_files = notes["files"]
    enclosures = sorted({p for p in note_files.values()})

    ledger = build_ledger(ctx, results, note_files)
    excluded, post = _scope_lists(store, ctx)
    attach_scope(ledger, excluded, post)

    labels = build_labels(ctx, results, resolution, note_files, outcome)
    plan_doc = build_generation_plan(ctx, results, outcome, resolution)
    form_pack = render_form(ctx, enclosures, resolution)

    case_dir = out_root / case_id
    if case_dir.exists():
        shutil.rmtree(case_dir)
    input_dir = case_dir / "input"
    gold_dir = case_dir / "gold"
    notes_dir = input_dir / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    gold_dir.mkdir(parents=True, exist_ok=True)

    for rel, text in notes["contents"].items():
        path = case_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    dump_yaml(input_dir / "pa_form.yaml", form_pack["form"], header=form_pack["_header"])
    dump_yaml(gold_dir / "ledger.yaml", ledger, header=f"# Generated ledger for {case_id}. Hidden from the verifier.")
    dump_yaml(gold_dir / "labels.yaml", labels, header=f"# Generated labels for {case_id}. Derived from the ledger, not the notes.")
    dump_yaml(gold_dir / "generation_plan.yaml", plan_doc, header=f"# Generation plan for {case_id}. Hidden from the verifier.")

    return {
        "case_id": case_id,
        "status": outcome["documentation_status"],
        "policy_id": policy_id,
        "variant": entry["variant"],
        "patient_id": entry["patient_id"],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Generate PA corpus cases into data/cases/")
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--case", help="Generate a single case_id")
    parser.add_argument("--rebuild-catalog", action="store_true")
    parser.add_argument("--output-root", type=Path, default=CASES_DIR)
    args = parser.parse_args(argv)

    store = SyntheaStore()
    if args.rebuild_catalog or not args.catalog.exists():
        write_catalog(store, args.catalog)
        print(f"Wrote catalog {args.catalog}")

    catalog = load_yaml(args.catalog)
    entries = catalog["cases"]
    if args.case:
        entries = [e for e in entries if e["case_id"] == args.case]
        if not entries:
            print(f"Case {args.case} not in catalog", file=sys.stderr)
            return 1

    summary = []
    for entry in entries:
        info = generate_one(store, entry, args.output_root)
        summary.append(info)
        print(f"{info['case_id']:22} {info['policy_id']:22} {info['variant']:24} {info['status']}")

    print(f"\nGenerated {len(summary)} cases into {args.output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
