"""Derive criterion labels from clinical facts + what is enclosed. Never from note prose."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .context import CaseContext


@dataclass
class CriterionResult:
    id: str
    label: str
    clinical_truth: str
    documentation_state: str
    reasoning: str
    remediable: Optional[bool] = None
    ledger_ids: List[str] = field(default_factory=list)


def _doc(enclosed: bool, clinical_met: bool, affirm_unmet: bool = False) -> str:
    if not enclosed:
        return "SILENT"
    if affirm_unmet or not clinical_met:
        return "AFFIRMATIVELY_UNMET" if not clinical_met else "ESTABLISHED"
    return "ESTABLISHED"


def _label(documentation_state: str, clinical_met: bool) -> str:
    if documentation_state == "SILENT":
        return "MISSING"
    if documentation_state == "AFFIRMATIVELY_UNMET" or not clinical_met:
        return "CONTRADICTED"
    return "SUPPORTED"


def _therapy_result(
    ctx: CaseContext,
    criterion_id: str,
    threshold_days: int,
    modality_required: str,
    region_required: Optional[str],
    lookback_days: int = 365,
) -> CriterionResult:
    f = ctx.facts
    r = ctx.render
    region_ok = region_required is None or f.pt_body_region == region_required
    recency_ok = True
    if f.pt_stop:
        recency_ok = (ctx.episode.request_date - f.pt_stop).days <= lookback_days
    duration_ok = f.pt_days is not None and f.pt_days >= threshold_days
    modality_ok = True
    if modality_required == "in_person":
        modality_ok = f.pt_modality == "in_person"
    clinical_met = bool(duration_ok and modality_ok and region_ok and recency_ok and f.pt_start)

    enclosed = r.enclose_pt
    if enclosed and f.pt_days is not None and not duration_ok:
        doc = "AFFIRMATIVELY_UNMET"
        clinical_met = False
    elif enclosed and not modality_ok:
        doc = "AFFIRMATIVELY_UNMET"
        clinical_met = False
    elif enclosed and not region_ok:
        # Wrong-joint PT does not establish the criterion.
        doc = "SILENT"
    elif enclosed and clinical_met:
        doc = "ESTABLISHED"
    elif enclosed and not clinical_met:
        doc = "AFFIRMATIVELY_UNMET"
    else:
        doc = "SILENT"

    label = _label(doc, clinical_met)
    bits = []
    if f.pt_days is not None:
        bits.append(f"course length {f.pt_days} days vs threshold {threshold_days}")
    else:
        bits.append("no therapy course on the ledger")
    bits.append(f"modality {f.pt_modality}")
    bits.append(f"body region {f.pt_body_region}")
    bits.append("enclosed" if enclosed else "not enclosed")
    return CriterionResult(
        id=criterion_id,
        label=label,
        clinical_truth="MET" if clinical_met else "NOT_MET",
        documentation_state=doc,
        reasoning="; ".join(bits) + ".",
        remediable=label == "MISSING",
        ledger_ids=["A005", "E004"] if f.pt_start else [],
    )


def evaluate_arthro(ctx: CaseContext) -> List[CriterionResult]:
    f, r = ctx.facts, ctx.render
    c1_clin = f.pain and f.mechanical
    c1_doc = "ESTABLISHED" if r.enclose_ortho or r.enclose_ed else "SILENT"
    c2_clin = f.kl_grade <= 2
    c2_doc = "ESTABLISHED" if (r.enclose_ed or r.enclose_mri) else "SILENT"
    if not c2_clin and c2_doc == "ESTABLISHED":
        c2_doc = "AFFIRMATIVELY_UNMET"
    c3_clin = f.mri_tear
    c3_doc = "ESTABLISHED" if r.enclose_mri else "SILENT"
    if r.enclose_mri and not f.mri_tear:
        c3_doc = "AFFIRMATIVELY_UNMET"
        c3_clin = False
    c4 = _therapy_result(ctx, "C4_conservative_therapy", 42, "in_person", "knee")
    return [
        CriterionResult("C1_symptoms", _label(c1_doc, c1_clin), "MET" if c1_clin else "NOT_MET", c1_doc,
                        "Pain and mechanical symptoms documented in the clinical notes." if c1_clin else "Mechanical symptoms not established."),
        CriterionResult("C2_oa_severity", _label(c2_doc, c2_clin), "MET" if c2_clin else "NOT_MET", c2_doc,
                        f"Kellgren-Lawrence grade {f.kl_grade} (allowance 0-2)."),
        CriterionResult("C3_radiologic_confirmation", _label(c3_doc, c3_clin), "MET" if c3_clin else "NOT_MET", c3_doc,
                        "MRI report enclosed confirming meniscal tear." if r.enclose_mri else "No MRI report enclosed. A plain film does not confirm a meniscal tear."),
        c4,
    ]


def evaluate_tka(ctx: CaseContext) -> List[CriterionResult]:
    f, r = ctx.facts, ctx.render
    c1_clin = f.kl_grade >= 3
    c1_doc = "ESTABLISHED" if r.enclose_ed or r.enclose_ortho else "SILENT"
    if c1_doc == "ESTABLISHED" and not c1_clin:
        c1_doc = "AFFIRMATIVELY_UNMET"
    c2_clin = f.function_impaired
    c2_doc = "ESTABLISHED" if r.enclose_ortho else "SILENT"
    c3 = _therapy_result(ctx, "C3_conservative_management", 90, "any", "knee")
    if ctx.spec.pt_duration_source == "authored_long" and r.enclose_pt:
        c3 = CriterionResult(
            "C3_conservative_management", "SUPPORTED", "MET", "ESTABLISHED",
            f"Authored therapy course of {f.pt_days} days (provenance authored; Synthea has no 90-day PT courses).",
            remediable=False, ledger_ids=["A005"],
        )
    c4_clin = f.infection_absent
    c4_doc = "ESTABLISHED" if r.enclose_followup and ctx.spec.document_infection_absent else "SILENT"
    return [
        CriterionResult("C1_advanced_oa", _label(c1_doc, c1_clin), "MET" if c1_clin else "NOT_MET", c1_doc,
                        f"Kellgren-Lawrence grade {f.kl_grade} (requires 3-4)."),
        CriterionResult("C2_functional_impairment", _label(c2_doc, c2_clin), "MET" if c2_clin else "NOT_MET", c2_doc,
                        "Function limited in daily activity." if c2_clin else "Function not documented as limited."),
        c3,
        CriterionResult("C4_no_active_infection", _label(c4_doc, c4_clin), "MET" if c4_clin else "NOT_MET", c4_doc,
                        "Infection status addressed as absent." if c4_doc == "ESTABLISHED" else "Infection status not addressed."),
    ]


def evaluate_shoulder(ctx: CaseContext) -> List[CriterionResult]:
    f, r = ctx.facts, ctx.render
    c1_clin = f.pain and f.exam_abnormal
    c1_doc = "ESTABLISHED" if r.enclose_ortho and f.exam_abnormal else ("SILENT" if not f.exam_abnormal else "ESTABLISHED")
    if not f.exam_abnormal:
        c1_doc = "SILENT"
        c1_clin = False
    c2_clin = f.cuff_tear
    c2_doc = "ESTABLISHED" if r.enclose_mri else "SILENT"
    if r.enclose_mri and not f.cuff_tear:
        c2_doc = "AFFIRMATIVELY_UNMET"
    c3 = _therapy_result(ctx, "C3_conservative_therapy", 42, "any", "shoulder")
    return [
        CriterionResult("C1_symptoms_and_exam", _label(c1_doc, c1_clin), "MET" if c1_clin else "NOT_MET", c1_doc,
                        "Shoulder pain with restricted motion on examination." if c1_clin else "Examination findings not enclosed."),
        CriterionResult("C2_imaging_confirmation", _label(c2_doc, c2_clin), "MET" if c2_clin else "NOT_MET", c2_doc,
                        "MRI/US confirming a cuff tear." if r.enclose_mri else "No MRI or ultrasound report enclosed."),
        c3,
    ]


def evaluate_knee_mri(ctx: CaseContext) -> List[CriterionResult]:
    f, r = ctx.facts, ctx.render
    # B2 acute trauma
    b2c1 = CriterionResult(
        "B2_C1_acute_injury",
        "SUPPORTED" if r.enclose_ed else "MISSING",
        "MET",
        "ESTABLISHED" if r.enclose_ed else "SILENT",
        "Acute traumatic knee injury described in the emergency note.",
    )
    b2c2_clin = f.effusion or f.locking
    b2c2_doc = "ESTABLISHED" if (r.enclose_ed and b2c2_clin) else "SILENT"
    b2c2 = CriterionResult(
        "B2_C2_objective_finding",
        _label(b2c2_doc, b2c2_clin),
        "MET" if b2c2_clin else "NOT_MET",
        b2c2_doc,
        "Effusion or inability to bear weight documented." if b2c2_clin and r.enclose_ed else "No effusion, locking, or weight-bearing failure documented.",
    )
    b1c1 = CriterionResult(
        "B1_C1_persistent_symptoms",
        "SUPPORTED" if r.enclose_ortho else "MISSING",
        "MET",
        "ESTABLISHED" if r.enclose_ortho else "SILENT",
        "Persistent knee pain through the episode.",
    )
    b1c2_clin = f.mechanical and f.exam_abnormal
    b1c2_doc = "ESTABLISHED" if r.enclose_ortho and b1c2_clin else "SILENT"
    b1c2 = CriterionResult(
        "B1_C2_suspected_derangement",
        _label(b1c2_doc, b1c2_clin),
        "MET" if b1c2_clin else "NOT_MET",
        b1c2_doc,
        "Mechanical symptoms or provocative exam recorded." if b1c2_clin else "No derangement findings documented.",
    )
    b1c3 = _therapy_result(ctx, "B1_C3_conservative_trial", 42, "any", "knee")
    results = [b2c1, b2c2, b1c1, b1c2, b1c3]
    return results


def evaluate_spine(ctx: CaseContext) -> List[CriterionResult]:
    f, r = ctx.facts, ctx.render
    b8_clin = f.trauma and f.plain_film_inconclusive
    b8_doc = "ESTABLISHED" if (r.enclose_ed and r.enclose_xray_note and f.plain_film_inconclusive) else "SILENT"
    b8 = CriterionResult(
        "B8_trauma_fracture",
        _label(b8_doc, b8_clin),
        "MET" if b8_clin else "NOT_MET",
        b8_doc,
        "Trauma mechanism plus inconclusive cervical films." if b8_doc == "ESTABLISHED" else "Inconclusive plain films not enclosed, so the trauma-fracture branch is not established.",
    )
    b9_clin = f.cord_suspected
    b9_doc = "ESTABLISHED" if (r.enclose_ed and f.cord_suspected) else "SILENT"
    b9 = CriterionResult(
        "B9_suspected_cord_injury",
        _label(b9_doc, b9_clin),
        "MET" if b9_clin else "NOT_MET",
        b9_doc,
        "Cord injury suspected in the emergency note." if b9_clin else "No cord-injury suspicion documented.",
    )
    return [b8, b9]


EVALUATORS = {
    "PA-KNEE-ARTHRO-001": evaluate_arthro,
    "PA-TKA-001": evaluate_tka,
    "PA-SHOULDER-RCR-001": evaluate_shoulder,
    "PA-KNEE-MRI-001": evaluate_knee_mri,
    "PA-SPINE-MRI-001": evaluate_spine,
}

DISJUNCTIVE = {"PA-KNEE-MRI-001", "PA-SPINE-MRI-001"}

BRANCHES = {
    "PA-KNEE-MRI-001": {
        "B2_acute_trauma_with_effusion": ["B2_C1_acute_injury", "B2_C2_objective_finding"],
        "B1_persistent_after_conservative": [
            "B1_C1_persistent_symptoms",
            "B1_C2_suspected_derangement",
            "B1_C3_conservative_trial",
        ],
    },
    "PA-SPINE-MRI-001": {
        "B8_trauma_fracture": ["B8_trauma_fracture"],
        "B9_suspected_cord_injury": ["B9_suspected_cord_injury"],
    },
}


def evaluate(ctx: CaseContext) -> List[CriterionResult]:
    fn = EVALUATORS[ctx.policy_id]
    return fn(ctx)


def project_outcome(ctx: CaseContext, results: List[CriterionResult], gate: str, exclusion_triggered: bool) -> dict:
    by_id = {r.id: r for r in results}
    if gate == "NO_AUTH_REQUIRED":
        status = "READY_FOR_SUBMISSION"
        return {
            "documentation_status": status,
            "remediable": None,
            "counts": {"SUPPORTED": 0, "MISSING": 0, "CONTRADICTED": 0},
            "payer_decision": "APPROVE",
            "logic": "gate_no_auth",
        }

    if ctx.policy_id in DISJUNCTIVE:
        branch_states = []
        for _bid, cids in BRANCHES[ctx.policy_id].items():
            labels = [by_id[c].label for c in cids if c in by_id]
            if not labels:
                continue
            if any(x == "CONTRADICTED" for x in labels) and not all(x == "SUPPORTED" for x in labels):
                # A contradicted child means this branch fails on substance if any required child is contradicted.
                if any(x == "CONTRADICTED" for x in labels):
                    branch_states.append("fails")
                    continue
            if all(x == "SUPPORTED" for x in labels):
                branch_states.append("met")
            elif any(x == "CONTRADICTED" for x in labels):
                branch_states.append("fails")
            else:
                branch_states.append("indeterminate")
        # Exclusion for advanced OA on knee MRI
        if exclusion_triggered:
            status = "REVIEW_NEEDED"
            logic = "exclusion"
        elif "met" in branch_states:
            status = "READY_FOR_SUBMISSION"
            logic = "disjunctive_met"
        elif "indeterminate" in branch_states:
            status = "NOT_READY"
            logic = "disjunctive_indeterminate"
        else:
            status = "REVIEW_NEEDED"
            logic = "disjunctive_fails"
        counts = {"SUPPORTED": 0, "MISSING": 0, "CONTRADICTED": 0}
        for r in results:
            counts[r.label] = counts.get(r.label, 0) + 1
    else:
        counts = {"SUPPORTED": 0, "MISSING": 0, "CONTRADICTED": 0}
        for r in results:
            counts[r.label] = counts.get(r.label, 0) + 1
        if exclusion_triggered or counts["CONTRADICTED"] > 0:
            status = "REVIEW_NEEDED"
            logic = "conjunctive_fails"
        elif counts["MISSING"] > 0:
            status = "NOT_READY"
            logic = "conjunctive_indeterminate"
        else:
            status = "READY_FOR_SUBMISSION"
            logic = "conjunctive_met"

    payer = {"READY_FOR_SUBMISSION": "APPROVE", "NOT_READY": "PEND", "REVIEW_NEEDED": "DENY"}[status]
    remediable = True if status == "NOT_READY" else (False if status == "REVIEW_NEEDED" else None)
    return {
        "documentation_status": status,
        "remediable": remediable,
        "counts": counts,
        "payer_decision": payer,
        "logic": logic,
    }


def exclusion_triggered(ctx: CaseContext) -> bool:
    if ctx.policy_id == "PA-KNEE-MRI-001" and ctx.facts.kl_grade >= 3:
        return True
    if ctx.policy_id == "PA-KNEE-ARTHRO-001" and False:
        return False
    return False
