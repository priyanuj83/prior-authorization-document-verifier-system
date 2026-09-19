from pathlib import Path

from src.case_loading import load_case, load_case_dir
from src.case_loading.boundary import assert_not_hidden_evaluation_path
from src.common.exceptions import HiddenEvaluationDataError
from src.common.paths import CASES_DIR
import pytest


def test_load_seed_case_reads_input_only() -> None:
    packet = load_case("KNEE-ARTHRO-0001")
    assert packet.case_id == "KNEE-ARTHRO-0001"
    assert packet.pa_request.plan_id == "HUMANA-COMMERCIAL-01"
    assert packet.pa_request.service_key == "knee_arthroscopy"
    assert packet.pa_request.submitted_date.isoformat() == "2014-04-16"
    assert packet.notes
    assert all(note.path.startswith("input/notes/") for note in packet.notes)
    assert not hasattr(packet, "labels")
    assert "gold" not in packet.case_dir.split("/")[-1]


def test_loader_refuses_hidden_evaluation_paths() -> None:
    gold_file = CASES_DIR / "KNEE-ARTHRO-0001" / "gold" / "labels.yaml"
    with pytest.raises(HiddenEvaluationDataError):
        assert_not_hidden_evaluation_path(gold_file, context="Case loader")


def test_load_case_dir_does_not_open_gold(tmp_path: Path, monkeypatch) -> None:
    case_dir = tmp_path / "CASE-X"
    input_dir = case_dir / "input"
    notes_dir = input_dir / "notes"
    gold_dir = case_dir / "gold"
    notes_dir.mkdir(parents=True)
    gold_dir.mkdir()
    (gold_dir / "labels.yaml").write_text("secret: 1\n")
    (input_dir / "pa_form.yaml").write_text(
        "\n".join(
            [
                "submitted_date: '2014-04-16'",
                "member:",
                "  name: Test",
                "  member_id: X",
                "  plan_id: PLAN-A",
                "requested_service:",
                "  description: Test service",
                "  service_key: knee_arthroscopy",
                "",
            ]
        )
    )
    (notes_dir / "note.md").write_text("Patient declined physical therapy.")

    opened = []
    real_open = Path.open

    def tracking_open(self, *args, **kwargs):
        opened.append(self.as_posix())
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", tracking_open)
    packet = load_case_dir(case_dir)
    assert packet.pa_request.plan_id == "PLAN-A"
    assert any("pa_form.yaml" in path for path in opened)
    assert all(
            part != "gold" for path in opened for part in Path(path).parts
        )
