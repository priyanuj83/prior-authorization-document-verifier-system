"""Attestation check result. Separate from policy labels and from retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.enums import AttestationVerdict


@dataclass(frozen=True)
class AttestationCheck:
    attestation_id: str
    verdict: Optional[AttestationVerdict]
    rationale: str
