"""Deterministic Policy Resolver.

Responsible for matching plan, service, and submission date against
policy effective windows. Not responsible for evaluating medical evidence.

When zero or more than one version applies, the resolver returns that
uncertainty explicitly instead of inventing a policy choice.
"""

from __future__ import annotations

from typing import List

from src.enums import PolicyResolverAction, PolicyResolverStatus
from src.policy_models.repository import PolicyRepository
from src.policy_models.models import PolicyVersion
from src.policy_resolution.matching import is_effective_on
from src.policy_resolution.models import PolicyResolutionRequest, PolicyResolutionResult


class CatalogPolicyResolver:
    """Resolve a case against a policy catalog using date-window rules."""

    def __init__(self, repository: PolicyRepository) -> None:
        self._repository = repository

    def resolve(self, request: PolicyResolutionRequest) -> PolicyResolutionResult:
        listed = self._repository.list_versions_for(
            request.plan_id, request.service_key
        )
        candidates: List[PolicyVersion] = [
            version
            for version in listed
            if is_effective_on(version, request.submitted_date)
        ]
        return _result_for_candidates(request, tuple(candidates))


def resolve_from_candidates(
    request: PolicyResolutionRequest,
    catalog_versions: List[PolicyVersion],
) -> PolicyResolutionResult:
    """Pure matching helper used by tests and the catalog resolver."""

    candidates = [
        version
        for version in catalog_versions
        if version.plan_id == request.plan_id
        and version.service_key == request.service_key
        and is_effective_on(version, request.submitted_date)
    ]
    return _result_for_candidates(request, tuple(candidates))


def _result_for_candidates(
    request: PolicyResolutionRequest,
    candidates: tuple,
) -> PolicyResolutionResult:
    submitted = request.submitted_date.isoformat()
    if len(candidates) == 1:
        version = candidates[0]
        return PolicyResolutionResult(
            status=PolicyResolverStatus.RESOLVED,
            submission_date=request.submitted_date,
            candidates=candidates,
            status_rationale=(
                f"Exactly one policy version applies on {submitted}: "
                f"{version.policy_id} v{version.version} for plan "
                f"{version.plan_id} / service {version.service_key}."
            ),
            recommended_action=PolicyResolverAction.START_VERIFICATION,
        )
    if len(candidates) == 0:
        return PolicyResolutionResult(
            status=PolicyResolverStatus.UNRESOLVED,
            submission_date=request.submitted_date,
            candidates=(),
            status_rationale=(
                f"No policy version applies for plan {request.plan_id}, "
                f"service {request.service_key}, on {submitted}. "
                "The system will not invent an applicable policy."
            ),
            recommended_action=PolicyResolverAction.MANUAL_REVIEW,
        )
    ids = ", ".join(
        f"{item.policy_id} v{item.version} "
        f"({item.effective_from.isoformat()} -> "
        f"{'open' if item.effective_to is None else item.effective_to.isoformat()})"
        for item in candidates
    )
    return PolicyResolutionResult(
        status=PolicyResolverStatus.MULTIPLE_MATCHES,
        submission_date=request.submitted_date,
        candidates=candidates,
        status_rationale=(
            f"Multiple policy versions appear applicable on {submitted} for "
            f"plan {request.plan_id} / service {request.service_key}: {ids}. "
            "The system will not arbitrarily choose one."
        ),
        recommended_action=PolicyResolverAction.MANUAL_REVIEW,
    )
