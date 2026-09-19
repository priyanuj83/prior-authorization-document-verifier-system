"""Hard boundary between verifier input and hidden evaluation data."""

from __future__ import annotations

from pathlib import Path

from src.common.exceptions import HiddenEvaluationDataError
from src.common.paths import HIDDEN_EVALUATION_DIR_NAME, HIDDEN_EVALUATION_FILENAMES


def assert_not_hidden_evaluation_path(path: Path, *, context: str) -> None:
    """Refuse any path that would expose gold evaluation artifacts."""

    resolved = Path(path)
    parts = {part.lower() for part in resolved.parts}
    if HIDDEN_EVALUATION_DIR_NAME in parts:
        raise HiddenEvaluationDataError(
            f"{context} refused path {resolved} because it includes hidden "
            f"evaluation directory {HIDDEN_EVALUATION_DIR_NAME!r}."
        )
    if resolved.name in HIDDEN_EVALUATION_FILENAMES:
        raise HiddenEvaluationDataError(
            f"{context} refused hidden evaluation file {resolved.name!r} at {resolved}."
        )


def assert_case_tree_excludes_gold(case_dir: Path) -> None:
    """Runtime loader may only read <case>/input/**."""

    assert_not_hidden_evaluation_path(case_dir, context="Case loader")
    gold_dir = case_dir / HIDDEN_EVALUATION_DIR_NAME
    if gold_dir.exists():
        # Presence is expected in the corpus. The loader must still never open it.
        return
