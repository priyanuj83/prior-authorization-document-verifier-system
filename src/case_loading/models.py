"""Runtime input models. These objects must never carry gold evaluation data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Tuple


@dataclass(frozen=True)
class Member:
    name: str
    member_id: str
    dob: Optional[date]
    sex: Optional[str]
    plan: Optional[str]
    plan_id: str


@dataclass(frozen=True)
class RequestingProvider:
    name: Optional[str] = None
    specialty: Optional[str] = None
    practice: Optional[str] = None
    npi: Optional[str] = None


@dataclass(frozen=True)
class RequestedService:
    description: str
    service_key: str
    laterality: Optional[str] = None
    setting: Optional[str] = None
    proposed_date: Optional[date] = None
    urgency: Optional[str] = None


@dataclass(frozen=True)
class Diagnosis:
    description: str
    snomed: Optional[str] = None
    onset_date: Optional[date] = None


@dataclass(frozen=True)
class Attestation:
    id: str
    text: str


@dataclass(frozen=True)
class RecordsScope:
    episode_start: Optional[date] = None
    episode_end: Optional[date] = None
    is_complete_chart: bool = False
    records_cover: Optional[str] = None


@dataclass(frozen=True)
class PriorAuthorizationRequest:
    """Model-visible prior-authorization request (input/pa_form.yaml)."""

    submitted_date: date
    member: Member
    requested_service: RequestedService
    diagnosis: Optional[Diagnosis] = None
    requesting_provider: Optional[RequestingProvider] = None
    attestations: Tuple[Attestation, ...] = ()
    enclosures: Tuple[str, ...] = ()
    records_scope: Optional[RecordsScope] = None
    form_type: Optional[str] = None

    @property
    def plan_id(self) -> str:
        return self.member.plan_id

    @property
    def service_key(self) -> str:
        return self.requested_service.service_key


@dataclass(frozen=True)
class ClinicalNote:
    """One submitted clinical document the verifier may inspect."""

    file: str
    path: str
    content: str


@dataclass(frozen=True)
class VerifierCaseInput:
    """The only case payload the verifier is allowed to see."""

    case_id: str
    case_dir: str
    pa_request: PriorAuthorizationRequest
    notes: Tuple[ClinicalNote, ...]
