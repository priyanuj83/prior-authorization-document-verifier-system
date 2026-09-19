"""Write gold/labels.yaml and gold/generation_plan.yaml."""

from __future__ import annotations

from typing import List

from . import CORPUS_VERSION, FORBIDDEN_VOCABULARY, GENERATOR_ID
from .context import CaseContext
from .labels import CriterionResult, project_outcome
from .yamlio import iso


def build_labels(
    ctx: CaseContext,
    results: List[CriterionResult],
    resolution: dict,
    note_files: dict,
    outcome: dict,
) -> dict:
    criteria = []
    for res in results:
        notes = []
        if res.id.startswith("C4") or res.id.endswith("conservative") or "therapy" in res.id or "C3_conservative" in res.id or res.id == "B1_C3_conservative_trial":
            if note_files.get("pt"):
                notes.append({"file": note_files["pt"], "locator": "attended twice weekly" if ctx.facts.pt_modality == "in_person" else "home exercise programme"})
            if note_files.get("ed"):
                notes.append({"file": note_files["ed"], "locator": "Referral placed today to the outpatient physiotherapy service"})
        if "oa" in res.id or res.id == "C2_oa_severity" or res.id == "C1_advanced_oa":
            if note_files.get("ed"):
                notes.append({"file": note_files["ed"], "locator": f"Kellgren-Lawrence grade {ctx.facts.kl_grade}"})
        if "radiologic" in res.id or res.id == "C2_imaging_confirmation" or res.id == "C3_radiologic_confirmation":
            if note_files.get("mri"):
                notes.append({"file": note_files["mri"]})
        criteria.append({
            "id": res.id,
            "label": res.label,
            "clinical_truth": res.clinical_truth,
            "documentation_state": res.documentation_state,
            "evidence": {"ledger": res.ledger_ids, "notes": notes},
            "reasoning": res.reasoning,
        })

    status = outcome["documentation_status"]
    remediable = outcome["remediable"]
    remediation = []
    if status == "NOT_READY":
        for res in results:
            if res.label == "MISSING":
                remediation.append({
                    "criterion": res.id,
                    "action": "Obtain the missing documentation that would establish this requirement.",
                    "blocking": True,
                })
    escalation = []
    if status == "REVIEW_NEEDED":
        escalation.append({
            "action": "Clinical review before submission.",
            "detail": "The enclosed record affirmatively conflicts with at least one requirement, or an exclusion applies.",
        })
        if ctx.policy_id == "PA-KNEE-ARTHRO-001" and ctx.facts.kl_grade >= 3:
            escalation.append({
                "action": "Consider PA-TKA-001",
                "detail": "Advanced osteoarthritis contradicts arthroscopy and supports arthroplasty.",
            })

    messages = {
        "READY_FOR_SUBMISSION": "Documentation appears to support the required criteria for this request.",
        "NOT_READY": "Not ready to submit. One or more required items cannot be verified from the enclosed records.",
        "REVIEW_NEEDED": "Requires clinical review before submission. The record affirmatively conflicts with a requirement.",
    }
    if resolution.get("gate_result") == "NO_AUTH_REQUIRED":
        messages["READY_FOR_SUBMISSION"] = (
            "Prior authorisation is not required for this plan on this date. Nothing to prepare under this policy."
        )

    return {
        "case_id": ctx.case_id,
        "policy_id": ctx.policy_id,
        "policy_version": "1.0.0",
        "labelled_by": GENERATOR_ID,
        "labelled_date": "2026-09-04",
        "policy_resolution": resolution,
        "criteria": criteria,
        "waivers": _waivers(ctx),
        "exclusions": _exclusions(ctx, outcome),
        "attestation_check": _attestations(ctx, note_files),
        "outcome": {
            "provider_view": {
                "documentation_status": status,
                "remediable": remediable,
                "reasoning": _reason(ctx, results, status, resolution),
                "remediation": remediation,
                "escalation": escalation,
                "provider_message": messages[status],
            },
            "payer_view": {
                "decision": outcome["payer_decision"],
                "note": "Derived, not scored.",
            },
            "criterion_label_counts": outcome["counts"],
        },
        "evaluation_notes": {
            "variant": ctx.variant_name,
            "generator": GENERATOR_ID,
        },
    }


def _reason(ctx, results, status, resolution) -> str:
    if resolution.get("gate_result") == "NO_AUTH_REQUIRED":
        return "Request date falls before the plan's authorisation effective date, or the service is not authorised on this plan."
    bits = ", ".join(f"{r.id}={r.label}" for r in results)
    return f"{status} from criterion labels: {bits}."


def _waivers(ctx: CaseContext) -> list:
    if ctx.policy_id == "PA-KNEE-ARTHRO-001":
        return [{
            "id": "W1_locked_knee",
            "state": "NOT_FIRED",
            "reasoning": "Locking may be present but a displaced bucket-handle tear is not documented.",
        }]
    if ctx.policy_id == "PA-SHOULDER-RCR-001":
        return [{
            "id": "W1_acute_traumatic_full_thickness",
            "state": "NOT_FIRED",
            "reasoning": "Waiver not used; therapy criterion is evaluated on its own.",
        }]
    if ctx.policy_id == "PA-TKA-001":
        return [{
            "id": "W1_structural_emergency",
            "state": "NOT_FIRED",
            "reasoning": "No periarticular fracture, AVN, or failed arthroplasty on the ledger.",
        }]
    return []


def _exclusions(ctx: CaseContext, outcome: dict) -> list:
    if ctx.policy_id == "PA-KNEE-MRI-001":
        fired = ctx.facts.kl_grade >= 3
        return [{
            "id": "X1_advanced_oa_only",
            "state": "TRIGGERED" if fired else "NOT_TRIGGERED",
            "reasoning": f"Kellgren-Lawrence grade {ctx.facts.kl_grade}.",
        }]
    if ctx.policy_id == "PA-KNEE-ARTHRO-001":
        return [
            {"id": "X1_diagnostic_only", "state": "NOT_TRIGGERED"},
            {"id": "X2_meniscal_root_tear", "state": "NOT_TRIGGERED"},
        ]
    return []


def _attestations(ctx: CaseContext, note_files: dict) -> list:
    pt = bool(note_files.get("pt"))
    over = ctx.render.overclaim_pt
    at_pt = "NOT_SUPPORTED" if over or not pt else "SUPPORTED"
    return [
        {"id": "AT1", "verdict": "SUPPORTED"},
        {"id": "AT2", "verdict": "SUPPORTED"},
        {"id": "AT3", "verdict": at_pt,
         "note": "Over-claim: form asserts completed therapy that the envelope does not contain." if over else None},
    ]


def build_generation_plan(ctx: CaseContext, results: List[CriterionResult], outcome: dict, resolution: dict) -> dict:
    return {
        "case_id": ctx.case_id,
        "corpus_version": CORPUS_VERSION,
        "generator": GENERATOR_ID,
        "seed": ctx.seed,
        "patient": {
            "synthea_patient_id": ctx.patient_id,
            "name": ctx.full_name,
            "sex": ctx.sex,
            "birthdate": iso(ctx.birthdate),
            "age_at_request": ctx.age,
        },
        "request": {
            "requested_service": ctx.service_description,
            "service_key": ctx.service_key,
            "request_date": iso(ctx.episode.request_date),
        },
        "plan_resolution": resolution,
        "variant": ctx.variant_name,
        "intended_documentation_status": outcome["documentation_status"],
        "intended_payer_view": outcome["payer_decision"],
        "criteria": [
            {
                "id": r.id,
                "intended_label": r.label,
                "realization": r.documentation_state,
            }
            for r in results
        ],
        "forbidden_vocabulary": list(FORBIDDEN_VOCABULARY),
    }
