"""Filesystem locations for runtime corpus data."""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
ROOT = PACKAGE_DIR.parents[1]
DATA_DIR = ROOT / "data"
CASES_DIR = DATA_DIR / "cases"
POLICIES_DIR = DATA_DIR / "policies"
PA_REQUIREMENTS_DIR = DATA_DIR / "pa_requirements"

HIDDEN_EVALUATION_DIR_NAME = "gold"
HIDDEN_EVALUATION_FILENAMES = frozenset(
    {
        "labels.yaml",
        "ledger.yaml",
        "generation_plan.yaml",
    }
)
