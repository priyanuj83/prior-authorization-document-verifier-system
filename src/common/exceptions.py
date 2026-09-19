"""Verifier-wide exceptions."""

from __future__ import annotations


class VerifierError(Exception):
    """Base class for Healthcare Evidence Verifier errors."""


class HiddenEvaluationDataError(VerifierError):
    """Raised when runtime code would touch gold / hidden evaluation files."""


class CaseLoadError(VerifierError):
    """Raised when a prior-authorization case cannot be loaded from input/."""


class PolicyCatalogError(VerifierError):
    """Raised when the policy catalog cannot be read."""


class AggregationError(VerifierError):
    """Raised when deterministic aggregation receives an invalid input."""
