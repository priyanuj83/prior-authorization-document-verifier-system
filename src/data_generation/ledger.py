"""Build gold/ledger.yaml from Synthea events + authored facts."""

from __future__ import annotations

from datetime import timedelta

from .context import CaseContext
from .episode import body_region_from_text
from .labels import CriterionResult
from .yamlio import iso


def _note_path(date, slug: str) -> str:
    return f"input/notes/{iso(date)}-{slug}.md"


def build_ledger(ctx: CaseContext, results, note_files: dict) -> dict:
    ep = ctx.episode
    f = ctx.facts
    events = []
    eid = 1

    def add_synthea(date, typ, **extra):
        nonlocal eid
        rec = {
            "id": f"E{eid:03d}",
            "date": iso(date),
            "type": typ,
            "provenance": "synthea",
            **extra,
        }
        events.append(rec)
        eid += 1
        return rec["id"]

    def add_authored(date, typ, **extra):
        nonlocal eid
        rec = {
            "id": f"A{eid:03d}",
            "date": iso(date) if date else None,
            "type": typ,
            "provenance": "authored",
            **extra,
        }
        events.append(rec)
        eid += 1
        return rec["id"]

    if ep.encounter_id:
        add_synthea(
            ep.index_date,
            "encounter",
            source={"file": "synthea_data/encounters.csv", "encounter_id": ep.encounter_id},
            encounter_class=ep.encounter_class,
            payer_id=ep.payer_id,
            rendered_in=[note_files.get("ed")] if note_files.get("ed") else [],
        )
    add_synthea(
        ep.index_date,
        "condition",
        source={"file": "synthea_data/conditions.csv"},
        description=ep.anchor_condition,
        code=ep.anchor_code,
        rendered_in=[p for p in [note_files.get("ed"), note_files.get("ortho")] if p],
    )
    if ep.oa_present and ep.oa_onset:
        add_synthea(
            ep.oa_onset,
            "condition",
            source={"file": "synthea_data/conditions.csv"},
            description="Osteoarthritis of knee",
            rendered_in=[p for p in [note_files.get("ed"), note_files.get("ortho")] if p],
        )
    if ep.pt and f.pt_provenance == "synthea":
        add_synthea(
            ep.pt["start_date"],
            "careplan",
            source={"file": "synthea_data/careplans.csv", "careplan_id": ep.pt.get("Id")},
            description="Physical therapy procedure",
            reason=ep.pt.get("REASONDESCRIPTION"),
            date_range={"start": iso(ep.pt["start_date"]), "stop": iso(ep.pt.get("stop_date"))},
            duration_days=ep.pt.get("duration_days"),
            rendered_in=[note_files["pt"]] if note_files.get("pt") else [],
        )

    add_authored(
        ep.index_date,
        "symptom",
        description=f"Pain of the {ep.laterality} {('shoulder' if ctx.policy_id=='PA-SHOULDER-RCR-001' else 'neck' if ctx.policy_id=='PA-SPINE-MRI-001' else 'knee')}",
        rendered_in=[p for p in [note_files.get("ed"), note_files.get("ortho")] if p],
    )
    if ctx.policy_id in ("PA-KNEE-ARTHRO-001", "PA-KNEE-MRI-001"):
        add_authored(
            ep.index_date + timedelta(days=12),
            "symptom",
            description="Mechanical catching" + (" and locking" if f.locking else ""),
            is_mechanical_symptom=f.mechanical,
            is_true_locking=f.locking,
            rendered_in=[note_files["ortho"]] if note_files.get("ortho") else [],
        )
    add_authored(
        ep.index_date,
        "imaging_grading",
        modality="xray",
        findings={"kellgren_lawrence_grade": f.kl_grade},
        rendered_in=[note_files.get("ed")] if note_files.get("ed") else [],
    )
    if note_files.get("mri"):
        add_authored(
            f.pt_stop + timedelta(days=8) if f.pt_stop else ep.request_date - timedelta(days=7),
            "imaging",
            modality="mri",
            description="Authored MRI — no MRI exists in synthea_data",
            rendered_in=[note_files["mri"]],
        )
    if f.pt_start:
        add_authored(
            None,
            "therapy_detail",
            date_range={"start": iso(f.pt_start), "end": iso(f.pt_stop)},
            attributes={
                "modality": f.pt_modality,
                "duration_days": f.pt_days,
                "body_region": f.pt_body_region,
                "sessions_attended": f.pt_sessions,
                "response": f.pt_response,
                "documentation_enclosed": bool(note_files.get("pt")),
            },
            rendered_in=[note_files["pt"]] if note_files.get("pt") else [],
        )

    lookback_start = ep.request_date - timedelta(days=365)
    excluded = []
    post = []
    store_like_totals = ctx.chart_totals
    # Exclusions filled by generate.py via store — placeholder filled in generate
    criterion_truth = {}
    for res in results:
        criterion_truth[res.id] = {
            "clinical_truth": res.clinical_truth,
            "documentation_state": res.documentation_state,
            "label_follows": res.label,
            "detail": res.reasoning,
        }

    return {
        "case_id": ctx.case_id,
        "ledger_version": "0.3.0",
        "generator": "template-v0.3",
        "patient": {
            "synthea_patient_id": ctx.patient_id,
            "name": f"{ctx.first} {ctx.last}",
            "sex": ctx.sex,
            "birthdate": iso(ctx.birthdate),
            "city": ctx.city,
            "state": ctx.state,
        },
        "episode": {
            "laterality": ep.laterality,
            "index_date": iso(ep.index_date),
            "request_date": iso(ep.request_date),
            "anchor_condition": ep.anchor_condition,
        },
        "scope": {
            "episode_window": {"start": iso(ep.index_date), "end": iso(ep.request_date)},
            "therapy_lookback_window": {
                "start": iso(lookback_start),
                "end": iso(ep.request_date),
            },
            "patient_chart_totals": store_like_totals,
            "excluded_from_packet": excluded,
            "excluded_because_post_request": {"events": post},
            "distractor_content": {
                "present": bool(note_files.get("distractor")),
            },
        },
        "events": events,
        "criterion_truth": criterion_truth,
    }


def attach_scope(ledger: dict, excluded, post_events) -> dict:
    ledger["scope"]["excluded_from_packet"] = excluded
    ledger["scope"]["excluded_because_post_request"] = {"events": post_events}
    return ledger
