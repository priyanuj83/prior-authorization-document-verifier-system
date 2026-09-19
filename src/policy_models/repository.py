"""Policy catalog protocols and filesystem-backed repository.

The repository joins plan authorization requirements with clinical
policy files into PolicyVersion records. Date-window matching is
intentionally left to the Policy Resolver.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Protocol, Sequence, Tuple

from src.common.dates import parse_date
from src.common.exceptions import PolicyCatalogError
from src.common.paths import PA_REQUIREMENTS_DIR, POLICIES_DIR
from src.common.yaml_io import load_yaml
from src.policy_models.models import (
    PolicyBranch,
    PolicyCriterion,
    PolicyDocument,
    PolicyExclusion,
    PolicyVersion,
    PolicyWaiver,
)


class PolicyRepository(Protocol):
    """Source of policy versions and structured policy documents."""

    def list_versions_for(
        self, plan_id: str, service_key: str
    ) -> Sequence[PolicyVersion]:
        """Return catalog rows for a plan/service, ignoring submission date."""

    def get_document(self, policy_id: str, version: str) -> PolicyDocument:
        """Return the structured clinical policy for a resolved version."""


class InMemoryPolicyRepository:
    """Test/fixture catalog that does not touch the filesystem."""

    def __init__(
        self,
        versions: Iterable[PolicyVersion],
        documents: Optional[Iterable[PolicyDocument]] = None,
    ) -> None:
        self._versions: Tuple[PolicyVersion, ...] = tuple(versions)
        self._documents: Dict[Tuple[str, str], PolicyDocument] = {
            (document.policy_id, document.version): document
            for document in (documents or ())
        }

    def list_versions_for(
        self, plan_id: str, service_key: str
    ) -> Sequence[PolicyVersion]:
        return tuple(
            version
            for version in self._versions
            if version.plan_id == plan_id and version.service_key == service_key
        )

    def get_document(self, policy_id: str, version: str) -> PolicyDocument:
        try:
            return self._documents[(policy_id, version)]
        except KeyError as exc:
            raise PolicyCatalogError(
                f"No structured policy document for {policy_id} v{version}"
            ) from exc


class FilesystemPolicyRepository:
    """Load PolicyVersion rows from pa_requirements/ plus policies/."""

    def __init__(
        self,
        requirements_dir: Path = PA_REQUIREMENTS_DIR,
        policies_dir: Path = POLICIES_DIR,
    ) -> None:
        self.requirements_dir = Path(requirements_dir)
        self.policies_dir = Path(policies_dir)
        self._documents: Dict[str, PolicyDocument] = {}
        self._versions: List[PolicyVersion] = []
        self._load()

    def list_versions_for(
        self, plan_id: str, service_key: str
    ) -> Sequence[PolicyVersion]:
        return tuple(
            version
            for version in self._versions
            if version.plan_id == plan_id and version.service_key == service_key
        )

    def get_document(self, policy_id: str, version: str) -> PolicyDocument:
        document = self._documents.get(policy_id)
        if document is None:
            raise PolicyCatalogError(f"Unknown policy_id {policy_id!r}")
        if document.version != version:
            raise PolicyCatalogError(
                f"Requested {policy_id} v{version}, catalog has v{document.version}"
            )
        return document

    def _load(self) -> None:
        if not self.policies_dir.exists():
            raise PolicyCatalogError(f"Policies directory not found: {self.policies_dir}")
        if not self.requirements_dir.exists():
            raise PolicyCatalogError(
                f"PA requirements directory not found: {self.requirements_dir}"
            )

        for policy_path in sorted(self.policies_dir.glob("*.yaml")):
            document = _document_from_yaml(load_yaml(policy_path))
            self._documents[document.policy_id] = document

        for plan_path in sorted(self.requirements_dir.glob("*.yaml")):
            plan = load_yaml(plan_path)
            plan_id = plan.get("plan_id")
            if not plan_id:
                continue
            plan_from = parse_date(plan.get("effective_from"))
            plan_to = parse_date(plan.get("effective_to"))
            for item in plan.get("requirements") or []:
                governing = item.get("governing_policy")
                service_key = item.get("service_key")
                if not governing or not service_key:
                    continue
                document = self._documents.get(governing)
                if document is None:
                    raise PolicyCatalogError(
                        f"Plan {plan_id} references unknown policy {governing}"
                    )
                effective_from = parse_date(item.get("effective_from")) or plan_from
                if effective_from is None:
                    raise PolicyCatalogError(
                        f"Missing effective_from for {plan_id}/{service_key}"
                    )
                effective_to = parse_date(item.get("effective_to"))
                if effective_to is None:
                    effective_to = plan_to
                self._versions.append(
                    PolicyVersion(
                        policy_id=document.policy_id,
                        version=document.version,
                        plan_id=plan_id,
                        service_key=service_key,
                        effective_from=effective_from,
                        effective_to=effective_to,
                    )
                )


def _document_from_yaml(raw: dict) -> PolicyDocument:
    criteria: List[PolicyCriterion] = []
    branches: List[PolicyBranch] = []

    for item in raw.get("criteria") or []:
        criteria.append(_criterion_from_yaml(item, branch_id=None))

    for branch in raw.get("branches") or []:
        branch_id = str(branch.get("id"))
        nested = list(branch.get("criteria") or [])
        if not nested:
            nested = [
                {
                    "id": branch.get("id"),
                    "text": branch.get("text"),
                    "type": branch.get("type"),
                    **{
                        key: value
                        for key, value in branch.items()
                        if key not in {"id", "text", "type", "criteria", "logic"}
                    },
                }
            ]
        branch_criterion_ids: List[str] = []
        for item in nested:
            criterion = _criterion_from_yaml(item, branch_id=branch_id)
            criteria.append(criterion)
            branch_criterion_ids.append(criterion.id)
        branches.append(
            PolicyBranch(
                id=branch_id,
                text=str(branch.get("text") or ""),
                logic=str(branch.get("logic") or "all_of"),
                criterion_ids=tuple(branch_criterion_ids),
            )
        )

    waivers = tuple(
        PolicyWaiver(
            id=str(item.get("id")),
            text=str(item.get("text") or ""),
            waives=tuple(item.get("waives") or ()),
            conditions=tuple(item.get("conditions") or ()),
        )
        for item in raw.get("waivers") or []
    )
    exclusions = tuple(
        PolicyExclusion(
            id=str(item.get("id")),
            text=str(item.get("text") or ""),
        )
        for item in raw.get("exclusions") or []
    )

    policy_id = raw.get("policy_id")
    version = raw.get("version")
    if not policy_id or not version:
        raise PolicyCatalogError("Policy YAML must include policy_id and version")

    return PolicyDocument(
        policy_id=str(policy_id),
        version=str(version),
        title=str(raw.get("title") or policy_id),
        logic=str(raw.get("logic") or "all_of"),
        criteria=tuple(criteria),
        waivers=waivers,
        exclusions=exclusions,
        branches=tuple(branches),
    )


def _criterion_from_yaml(item: dict, branch_id: Optional[str]) -> PolicyCriterion:
    criterion_id = item.get("id")
    if not criterion_id:
        raise PolicyCatalogError("Policy criterion is missing an id")
    metadata = {
        key: value
        for key, value in item.items()
        if key not in {"id", "text", "type", "required", "waived_if"}
    }
    return PolicyCriterion(
        id=str(criterion_id),
        text=str(item.get("text") or ""),
        type=item.get("type"),
        required=bool(item.get("required", True)),
        branch_id=branch_id,
        waived_if=item.get("waived_if"),
        metadata=metadata,
    )
