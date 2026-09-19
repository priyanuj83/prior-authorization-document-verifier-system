"""Load prior-authorization cases from input/ only.

Gold labels, ledgers, and generation plans are structurally out of reach
of this loader. Evaluation code that needs those files lives in
src.evaluation and must not be called from the verifier pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from src.case_loading.boundary import assert_not_hidden_evaluation_path
from src.case_loading.models import (
    Attestation,
    ClinicalNote,
    Diagnosis,
    Member,
    PriorAuthorizationRequest,
    RecordsScope,
    RequestedService,
    RequestingProvider,
    VerifierCaseInput,
)
from src.common.dates import parse_date, require_date
from src.common.exceptions import CaseLoadError
from src.common.paths import CASES_DIR
from src.common.yaml_io import load_yaml


def load_case(case_id: str, cases_dir: Path = CASES_DIR) -> VerifierCaseInput:
    """Load the model-visible packet for a case id."""

    case_dir = Path(cases_dir) / case_id
    return load_case_dir(case_dir, case_id=case_id)


def load_case_dir(
    case_dir: Path, case_id: Optional[str] = None
) -> VerifierCaseInput:
    """Load a case from its root directory, reading only input/."""

    case_dir = Path(case_dir).resolve()
    if not case_dir.is_dir():
        raise CaseLoadError(f"Case directory does not exist: {case_dir}")

    resolved_id = case_id or case_dir.name
    input_dir = case_dir / "input"
    if not input_dir.is_dir():
        raise CaseLoadError(f"Case {resolved_id} has no input/ directory")

    assert_not_hidden_evaluation_path(input_dir, context="Case loader")

    form_path = input_dir / "pa_form.yaml"
    assert_not_hidden_evaluation_path(form_path, context="Case loader")
    if not form_path.is_file():
        raise CaseLoadError(f"Case {resolved_id} is missing input/pa_form.yaml")

    pa_request = _load_pa_request(form_path)
    notes = _load_notes(input_dir / "notes", case_dir)
    return VerifierCaseInput(
        case_id=resolved_id,
        case_dir=str(case_dir),
        pa_request=pa_request,
        notes=tuple(notes),
    )


def _load_pa_request(form_path: Path) -> PriorAuthorizationRequest:
    raw = load_yaml(form_path) or {}
    member_raw = raw.get("member") or {}
    service_raw = raw.get("requested_service") or {}
    diagnosis_raw = raw.get("diagnosis") or {}
    primary = diagnosis_raw.get("primary") or diagnosis_raw
    provider_raw = raw.get("requesting_provider") or {}
    scope_raw = raw.get("records_scope") or {}

    plan_id = member_raw.get("plan_id")
    service_key = service_raw.get("service_key")
    if not plan_id:
        raise CaseLoadError(f"{form_path} is missing member.plan_id")
    if not service_key:
        raise CaseLoadError(
            f"{form_path} is missing requested_service.service_key"
        )

    diagnosis = None
    if primary.get("description"):
        diagnosis = Diagnosis(
            description=str(primary.get("description")),
            snomed=str(primary["snomed"]) if primary.get("snomed") else None,
            onset_date=parse_date(diagnosis_raw.get("onset_date")),
        )

    attestations = tuple(
        Attestation(id=str(item.get("id")), text=str(item.get("text") or "").strip())
        for item in raw.get("attestations") or []
        if item.get("id")
    )

    return PriorAuthorizationRequest(
        submitted_date=require_date(raw.get("submitted_date"), "submitted_date"),
        member=Member(
            name=str(member_raw.get("name") or ""),
            member_id=str(member_raw.get("member_id") or ""),
            dob=parse_date(member_raw.get("dob")),
            sex=member_raw.get("sex"),
            plan=member_raw.get("plan"),
            plan_id=str(plan_id),
        ),
        requested_service=RequestedService(
            description=str(service_raw.get("description") or service_key),
            service_key=str(service_key),
            laterality=service_raw.get("laterality"),
            setting=service_raw.get("setting"),
            proposed_date=parse_date(service_raw.get("proposed_date")),
            urgency=service_raw.get("urgency"),
        ),
        diagnosis=diagnosis,
        requesting_provider=RequestingProvider(
            name=provider_raw.get("name"),
            specialty=provider_raw.get("specialty"),
            practice=provider_raw.get("practice"),
            npi=provider_raw.get("npi"),
        ),
        attestations=attestations,
        enclosures=tuple(str(item) for item in raw.get("enclosures") or []),
        records_scope=RecordsScope(
            episode_start=parse_date(scope_raw.get("episode_start")),
            episode_end=parse_date(scope_raw.get("episode_end")),
            is_complete_chart=bool(scope_raw.get("is_complete_chart", False)),
            records_cover=scope_raw.get("records_cover"),
        ),
        form_type=raw.get("form_type"),
    )


def _load_notes(notes_dir: Path, case_dir: Path) -> List[ClinicalNote]:
    if not notes_dir.exists():
        return []
    if not notes_dir.is_dir():
        raise CaseLoadError(f"Expected a notes directory at {notes_dir}")

    notes: List[ClinicalNote] = []
    for path in sorted(notes_dir.glob("*.md")):
        assert_not_hidden_evaluation_path(path, context="Case loader")
        relative = path.relative_to(case_dir).as_posix()
        notes.append(
            ClinicalNote(
                file=path.name,
                path=relative,
                content=path.read_text(encoding="utf-8"),
            )
        )
    return notes
