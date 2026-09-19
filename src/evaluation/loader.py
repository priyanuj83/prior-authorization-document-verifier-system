"""Load hidden gold evaluation data.

This module is the only runtime path allowed to read gold/. Verifier
components (case loading, resolution, verification, aggregation, pipeline)
must not import it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from src.common.paths import CASES_DIR, HIDDEN_EVALUATION_DIR_NAME
from src.common.yaml_io import load_yaml
from src.evaluation.models import GoldCriterionLabel, GoldEvaluationPacket, GoldLabels


def load_gold_packet(
    case_id: str, cases_dir: Path = CASES_DIR
) -> GoldEvaluationPacket:
    return load_gold_packet_from_dir(Path(cases_dir) / case_id, case_id=case_id)


def load_gold_packet_from_dir(
    case_dir: Path, case_id: Optional[str] = None
) -> GoldEvaluationPacket:
    case_dir = Path(case_dir)
    resolved_id = case_id or case_dir.name
    gold_dir = case_dir / HIDDEN_EVALUATION_DIR_NAME
    labels_path = gold_dir / "labels.yaml"
    if not labels_path.is_file():
        raise FileNotFoundError(f"Missing gold labels for {resolved_id}: {labels_path}")

    labels_raw = load_yaml(labels_path) or {}
    labels = _labels_from_yaml(labels_raw, fallback_case_id=resolved_id)
    return GoldEvaluationPacket(
        case_id=resolved_id,
        labels=labels,
        ledger=_optional_yaml(gold_dir / "ledger.yaml"),
        generation_plan=_optional_yaml(gold_dir / "generation_plan.yaml"),
    )


def _optional_yaml(path: Path) -> Optional[Any]:
    if not path.is_file():
        return None
    return load_yaml(path)


def _labels_from_yaml(raw: dict, fallback_case_id: str) -> GoldLabels:
    outcome = raw.get("outcome") or {}
    provider_view = outcome.get("provider_view") or {}
    criteria = tuple(
        GoldCriterionLabel(
            id=str(item.get("id")),
            label=str(item.get("label")),
            reasoning=item.get("reasoning"),
        )
        for item in raw.get("criteria") or []
    )
    return GoldLabels(
        case_id=str(raw.get("case_id") or fallback_case_id),
        policy_id=raw.get("policy_id"),
        policy_version=raw.get("policy_version"),
        criteria=criteria,
        provider_documentation_status=provider_view.get("documentation_status"),
        raw=raw,
    )
