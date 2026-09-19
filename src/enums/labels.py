"""Canonical vocabularies for the Healthcare Evidence Verifier.

These enums are the machine-readable contracts from the architecture
document. Downstream code must not invent additional labels for the
same decisions.
"""

from __future__ import annotations

from enum import Enum


class AtomicLabel(str, Enum):
    """Label assigned to one atomic sub-requirement."""

    PROVEN = "PROVEN"
    NOT_PROVEN = "NOT_PROVEN"
    REFUTED = "REFUTED"


class CriterionLabel(str, Enum):
    """Label assigned to one policy criterion after aggregation."""

    SUPPORTED = "SUPPORTED"
    MISSING = "MISSING"
    CONTRADICTED = "CONTRADICTED"


class CaseStatus(str, Enum):
    """Provider-side overall status for a prior-authorization packet.

    READY_FOR_SUBMISSION does not mean insurance approval, medical
    approval, or guaranteed coverage. It means the submitted evidence
    appears complete relative to the evaluated policy criteria.
    """

    READY_FOR_SUBMISSION = "READY_FOR_SUBMISSION"
    DOCUMENTATION_INCOMPLETE = "DOCUMENTATION_INCOMPLETE"
    NEEDS_CLINICAL_REVIEW = "NEEDS_CLINICAL_REVIEW"


class PolicyResolverStatus(str, Enum):
    """What happened during policy-version matching."""

    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"
    MULTIPLE_MATCHES = "MULTIPLE_MATCHES"


class PolicyResolverAction(str, Enum):
    """What should happen next after policy resolution."""

    START_VERIFICATION = "START_VERIFICATION"
    MANUAL_REVIEW = "MANUAL_REVIEW"
