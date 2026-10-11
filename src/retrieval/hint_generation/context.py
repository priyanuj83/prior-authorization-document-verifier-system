"""Build neutral case context. Provider attestations are not copied."""

from __future__ import annotations

from datetime import timedelta

from src.case_loading.models import PriorAuthorizationRequest
from src.requirement_models.models import AtomicSubRequirement
from src.retrieval.query_models.models import DateRange, NeutralCaseContext

_SERVICE_BODY_PART = {
    "knee_arthroscopy": "knee",
    "knee_mri": "knee",
    "total_knee_arthroplasty": "knee",
    "rotator_cuff_repair": "shoulder",
    "spine_mri_ct": "spine",
}


def build_neutral_case_context(
    case_id: str,
    request: PriorAuthorizationRequest,
) -> NeutralCaseContext:
    scope = request.records_scope
    diagnosis = request.diagnosis.description if request.diagnosis else None
    return NeutralCaseContext(
        case_id=case_id,
        patient_id=request.member.member_id,
        service_key=request.service_key,
        requested_service=request.requested_service.description,
        body_part=_SERVICE_BODY_PART.get(request.service_key),
        laterality=request.requested_service.laterality,
        diagnosis=diagnosis,
        submitted_date=request.submitted_date,
        episode_start=scope.episode_start if scope else None,
        episode_end=scope.episode_end if scope else None,
    )


def date_range_for(
    context: NeutralCaseContext,
    requirement: AtomicSubRequirement,
) -> DateRange:
    """Hint window only. It is not a hard filter unless policy says so."""

    lookback = requirement.semantics.lookback_days
    if lookback is not None:
        return DateRange(
            start=context.submitted_date - timedelta(days=lookback),
            end=context.submitted_date,
        )
    return DateRange(start=context.episode_start, end=context.episode_end)
