"""Deterministic policy effective-window matching.

A version applies only when:

    effective_from <= submitted_date

and:

    effective_to is null OR submitted_date <= effective_to
"""

from __future__ import annotations

from datetime import date

from src.policy_models.models import PolicyVersion


def is_effective_on(version: PolicyVersion, submitted_date: date) -> bool:
    if submitted_date < version.effective_from:
        return False
    if version.effective_to is not None and submitted_date > version.effective_to:
        return False
    return True
