"""Render input/pa_form.yaml. Attestations are claims, not truth."""

from __future__ import annotations

from datetime import timedelta

from .context import CaseContext
from .yamlio import iso


PLAN_TITLES = {
    "HUMANA-COMMERCIAL-01": "Humana Commercial HMO",
    "AETNA-COMMERCIAL-01": "Aetna Commercial PPO",
    "MEDICARE-FFS-01": "Medicare fee-for-service",
}


def render_form(ctx: CaseContext, enclosures, resolution: dict) -> dict:
    ep = ctx.episode
    f = ctx.facts
    side = ep.laterality
    joint = _side_joint(ctx)
    over = ctx.render.overclaim_pt
    pt_enclosed = any("pt-discharge" in e for e in enclosures)
    mri_enclosed = any("mri-report" in e for e in enclosures)

    at4_true = (
        f"The patient completed a supervised outpatient physiotherapy course for the {joint}, "
        f"attending twice weekly, without resolution. The therapy discharge summary is enclosed."
    )
    at4_over = (
        f"The patient completed a course of physical therapy for the {joint} without resolution."
    )

    attestations = [
        {"id": "AT1", "text": f"The patient has persistent {joint} pain"
         + (" with mechanical catching." if f.mechanical else ".")},
        {"id": "AT2", "text": _imaging_attestation(ctx, mri_enclosed)},
        {"id": "AT3", "text": at4_over if over else (at4_true if pt_enclosed else
            f"Conservative measures have been tried for the {joint}.")},
    ]

    header = f"""# SUBMITTED PRIOR AUTHORISATION REQUEST: {ctx.case_id}
# Generated packet. This file plus input/notes/ is the CASE-SPECIFIC input.
# The applicable policy is resolved from member.plan_id + requested_service.service_key + submitted_date.
# gold/ is hidden from the verifier.
"""
    return {
        "_header": header,
        "form": {
            "form_type": "prior_authorisation_request",
            "submitted_date": iso(ep.request_date),
            "generator": "template-v0.3",
            "member": {
                "name": ctx.full_name,
                "member_id": ctx.mrn,
                "dob": iso(ctx.birthdate),
                "sex": ctx.sex,
                "plan": PLAN_TITLES.get(ctx.plan_id, ctx.plan_id),
                "plan_id": ctx.plan_id,
            },
            "requesting_provider": {
                "name": ctx.provider[0],
                "specialty": ctx.provider[1],
                "practice": ctx.provider[2],
                "npi": ctx.provider[3],
            },
            "requested_service": {
                "description": ctx.service_description,
                "service_key": ctx.service_key,
                "laterality": side if ctx.policy_id != "PA-SPINE-MRI-001" else None,
                "setting": "outpatient",
                "proposed_date": iso(ep.request_date + timedelta(days=21)),
                "urgency": "routine",
            },
            "diagnosis": {
                "primary": {
                    "description": ctx.diagnosis_description,
                    "snomed": str(ctx.diagnosis_snomed) if ctx.diagnosis_snomed else None,
                },
                "onset_date": iso(ep.index_date),
            },
            "attestations": attestations,
            "enclosures": enclosures,
            "records_scope": {
                "episode_start": iso(ep.index_date),
                "episode_end": iso(ep.request_date),
                "is_complete_chart": False,
            },
        },
    }


def _side_joint(ctx: CaseContext) -> str:
    if ctx.policy_id == "PA-SHOULDER-RCR-001":
        return f"{ctx.episode.laterality} shoulder"
    if ctx.policy_id == "PA-SPINE-MRI-001":
        return "neck"
    return f"{ctx.episode.laterality} knee"


def _imaging_attestation(ctx: CaseContext, mri_enclosed: bool) -> str:
    side = ctx.episode.laterality
    if ctx.policy_id == "PA-KNEE-ARTHRO-001":
        if mri_enclosed:
            return f"MRI of the {side} knee confirms a meniscal tear."
        return f"Imaging of the {side} knee has been obtained."
    if ctx.policy_id == "PA-TKA-001":
        return f"Plain radiographs demonstrate advanced osteoarthritis of the {side} knee."
    if ctx.policy_id == "PA-SHOULDER-RCR-001":
        if mri_enclosed:
            return f"MRI confirms a rotator cuff tear of the {side} shoulder."
        return f"Cuff tear is suspected on clinical examination of the {side} shoulder."
    if ctx.policy_id == "PA-SPINE-MRI-001":
        return "Cervical radiographs after trauma are not conclusive."
    return f"Advanced imaging of the {side} knee is requested."
