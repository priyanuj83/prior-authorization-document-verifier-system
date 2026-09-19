from __future__ import annotations

from datetime import date
from typing import Optional

from src.enums import PolicyResolverAction, PolicyResolverStatus
from src.policy_models.models import PolicyVersion
from src.policy_models.repository import FilesystemPolicyRepository
from src.policy_resolution.matching import is_effective_on
from src.policy_resolution.models import PolicyResolutionRequest
from src.policy_resolution.resolver import CatalogPolicyResolver, resolve_from_candidates


def _version(
    policy_id: str,
    version: str,
    plan_id: str,
    service_key: str,
    effective_from: str,
    effective_to: Optional[str],
) -> PolicyVersion:
    return PolicyVersion(
        policy_id=policy_id,
        version=version,
        plan_id=plan_id,
        service_key=service_key,
        effective_from=date.fromisoformat(effective_from),
        effective_to=None if effective_to is None else date.fromisoformat(effective_to),
    )


def test_effective_window_includes_boundaries() -> None:
    version = _version(
        "POL", "1", "PLAN", "svc", "2024-01-01", "2024-12-31"
    )
    assert is_effective_on(version, date(2024, 1, 1))
    assert is_effective_on(version, date(2024, 12, 31))
    assert not is_effective_on(version, date(2023, 12, 31))
    assert not is_effective_on(version, date(2025, 1, 1))


def test_open_ended_version_applies_after_effective_from() -> None:
    version = _version("POL", "2", "PLAN", "svc", "2025-02-01", None)
    assert not is_effective_on(version, date(2025, 1, 15))
    assert is_effective_on(version, date(2025, 2, 1))
    assert is_effective_on(version, date(2026, 1, 1))


def test_policy_gap_is_unresolved_and_keeps_empty_candidates() -> None:
    """Architecture section 20: do not silently pick V1 or V2."""

    catalog = [
        _version("POL", "1.0", "PLAN-A", "knee_arthroscopy", "2024-01-01", "2024-12-31"),
        _version("POL", "2.0", "PLAN-A", "knee_arthroscopy", "2025-02-01", None),
    ]
    result = resolve_from_candidates(
        PolicyResolutionRequest("PLAN-A", "knee_arthroscopy", date(2025, 1, 15)),
        catalog,
    )
    assert result.status is PolicyResolverStatus.UNRESOLVED
    assert result.recommended_action is PolicyResolverAction.MANUAL_REVIEW
    assert result.candidates == ()
    assert result.selected_version is None
    assert result.submission_date == date(2025, 1, 15)


def test_overlapping_versions_are_multiple_matches() -> None:
    """Architecture section 21: do not arbitrarily choose one."""

    catalog = [
        _version("POL", "1.0", "PLAN-A", "knee_arthroscopy", "2025-01-01", "2025-12-31"),
        _version("POL", "2.0", "PLAN-A", "knee_arthroscopy", "2025-06-01", "2026-05-31"),
    ]
    result = resolve_from_candidates(
        PolicyResolutionRequest("PLAN-A", "knee_arthroscopy", date(2025, 8, 10)),
        catalog,
    )
    assert result.status is PolicyResolverStatus.MULTIPLE_MATCHES
    assert result.recommended_action is PolicyResolverAction.MANUAL_REVIEW
    assert len(result.candidates) == 2
    assert result.selected_version is None


def test_single_match_is_resolved_and_starts_verification() -> None:
    catalog = [
        _version("POL", "1.0", "PLAN-A", "knee_arthroscopy", "2024-01-01", "2024-12-31"),
        _version("POL", "2.0", "PLAN-A", "knee_arthroscopy", "2025-02-01", None),
    ]
    result = resolve_from_candidates(
        PolicyResolutionRequest("PLAN-A", "knee_arthroscopy", date(2024, 6, 1)),
        catalog,
    )
    assert result.status is PolicyResolverStatus.RESOLVED
    assert result.recommended_action is PolicyResolverAction.START_VERIFICATION
    assert len(result.candidates) == 1
    assert result.selected_version is not None
    assert result.selected_version.version == "1.0"


def test_unrelated_plan_or_service_does_not_match() -> None:
    catalog = [
        _version("POL", "1.0", "PLAN-A", "knee_arthroscopy", "2024-01-01", None),
    ]
    other_plan = resolve_from_candidates(
        PolicyResolutionRequest("PLAN-B", "knee_arthroscopy", date(2024, 6, 1)),
        catalog,
    )
    other_service = resolve_from_candidates(
        PolicyResolutionRequest("PLAN-A", "knee_mri", date(2024, 6, 1)),
        catalog,
    )
    assert other_plan.status is PolicyResolverStatus.UNRESOLVED
    assert other_service.status is PolicyResolverStatus.UNRESOLVED


def test_filesystem_resolver_matches_humana_knee_arthroscopy_seed_case() -> None:
    resolver = CatalogPolicyResolver(FilesystemPolicyRepository())
    result = resolver.resolve(
        PolicyResolutionRequest(
            plan_id="HUMANA-COMMERCIAL-01",
            service_key="knee_arthroscopy",
            submitted_date=date(2014, 4, 16),
        )
    )
    assert result.status is PolicyResolverStatus.RESOLVED
    assert result.selected_version is not None
    assert result.selected_version.policy_id == "PA-KNEE-ARTHRO-001"


def test_filesystem_resolver_unresolved_before_humana_effective_date() -> None:
    resolver = CatalogPolicyResolver(FilesystemPolicyRepository())
    result = resolver.resolve(
        PolicyResolutionRequest(
            plan_id="HUMANA-COMMERCIAL-01",
            service_key="knee_arthroscopy",
            submitted_date=date(2013, 1, 1),
        )
    )
    assert result.status is PolicyResolverStatus.UNRESOLVED
    assert result.candidates == ()
    assert result.recommended_action is PolicyResolverAction.MANUAL_REVIEW
