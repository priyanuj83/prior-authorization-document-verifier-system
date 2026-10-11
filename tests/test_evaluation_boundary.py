from __future__ import annotations

import ast
from pathlib import Path

from src.common.paths import CASES_DIR, ROOT
from src.evaluation import load_gold_packet

VERIFIER_PACKAGES = (
    "src/case_loading",
    "src/policy_resolution",
    "src/policy_models",
    "src/requirement_models",
    "src/policy_decomposition",
    "src/atomic_verification",
    "src/indexing",
    "src/retrieval",
    "src/clinical_extraction",
    "src/reasoning",
    "src/attestation_verification",
    "src/criterion_aggregation",
    "src/case_aggregation",
    "src/pipeline",
)


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_verifier_packages_do_not_import_evaluation() -> None:
    offenders = []
    for package in VERIFIER_PACKAGES:
        package_dir = ROOT / package
        for path in package_dir.rglob("*.py"):
            for name in _imported_modules(path):
                if name == "src.evaluation" or name.startswith("src.evaluation."):
                    offenders.append(f"{path.relative_to(ROOT)} imports {name}")
    assert offenders == []


def test_gold_loader_reads_hidden_labels() -> None:
    packet = load_gold_packet("KNEE-ARTHRO-0001")
    assert packet.case_id == "KNEE-ARTHRO-0001"
    assert packet.labels.policy_id == "PA-KNEE-ARTHRO-001"
    assert packet.labels.criteria
    assert (CASES_DIR / "KNEE-ARTHRO-0001" / "gold" / "labels.yaml").is_file()
    assert packet.ledger is not None
    assert packet.generation_plan is not None
