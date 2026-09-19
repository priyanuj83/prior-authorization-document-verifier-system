"""Resolve plan_id + service_key + request_date to a gate result and governing policy."""

from datetime import date
from typing import Optional

from .paths import PA_REQUIREMENTS_DIR, POLICIES_DIR
from .yamlio import iso, load_yaml

SERVICE_KEYS = {
    "PA-KNEE-ARTHRO-001": "knee_arthroscopy",
    "PA-KNEE-MRI-001": "knee_mri",
    "PA-TKA-001": "total_knee_arthroplasty",
    "PA-SHOULDER-RCR-001": "rotator_cuff_repair",
    "PA-SPINE-MRI-001": "spine_mri_ct",
}

PAYER_TO_PLAN = {
    "Humana": "HUMANA-COMMERCIAL-01",
    "Aetna": "AETNA-COMMERCIAL-01",
    "Medicare": "MEDICARE-FFS-01",
    "Dual Eligible": "MEDICARE-FFS-01",
    "Medicaid": "MEDICARE-FFS-01",
}


def plan_id_for_payer(payer_name: str, patient_id: str = "") -> str:
    if payer_name in PAYER_TO_PLAN:
        return PAYER_TO_PLAN[payer_name]
    # Other commercial payers overlay onto Aetna or Humana by patient id.
    if patient_id and int(patient_id.replace("-", "")[:8], 16) % 2 == 0:
        return "HUMANA-COMMERCIAL-01"
    return "AETNA-COMMERCIAL-01"


def load_plan(plan_id: str) -> dict:
    path = PA_REQUIREMENTS_DIR / f"{plan_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No PA requirements file for {plan_id}")
    return load_yaml(path)


def load_policy(policy_id: str) -> dict:
    path = POLICIES_DIR / f"{policy_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No policy file for {policy_id}")
    return load_yaml(path)


def _parse_date(value) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def resolve(plan_id: str, service_key: str, request_date) -> dict:
    """Return gate_result and governing policy. Deterministic; no clinical facts."""
    req_date = _parse_date(request_date)
    plan = load_plan(plan_id)
    match = None
    for item in plan.get("requirements") or []:
        if item.get("service_key") == service_key:
            match = item
            break
    if match is None:
        raise KeyError(f"Service {service_key} not listed on plan {plan_id}")

    effective = _parse_date(match.get("effective_from") or plan.get("effective_from"))
    in_force = True
    if effective and req_date and req_date < effective:
        in_force = False

    requires_auth = bool(match.get("requires_prior_auth")) and in_force
    requires_review = bool(match.get("requires_coverage_review"))
    governing = match.get("governing_policy")

    if requires_auth:
        gate = "AUTH_REQUIRED"
    elif requires_review:
        gate = "COVERAGE_REVIEW_REQUIRED"
    else:
        gate = "NO_AUTH_REQUIRED"
        governing = governing if requires_review else match.get("governing_policy")
        if not requires_auth and not requires_review:
            governing = None

    # Coverage-review path still uses the clinical policy.
    if gate == "COVERAGE_REVIEW_REQUIRED":
        governing = match.get("governing_policy")
    if gate == "AUTH_REQUIRED":
        governing = match.get("governing_policy")

    return {
        "resolved_from": {
            "plan_id": plan_id,
            "service_key": service_key,
            "request_date": iso(req_date),
        },
        "requires_prior_auth": bool(match.get("requires_prior_auth")) if in_force else False,
        "requires_coverage_review": match.get("requires_coverage_review"),
        "requirement_effective_from": iso(effective) if effective else None,
        "gate_result": gate,
        "governing_policy": governing,
        "review_type": match.get("review_type"),
        "plan_name": plan.get("plan_name"),
        "synthea_payer_id": plan.get("synthea_payer_id"),
    }
