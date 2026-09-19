from src.policy_models.repository import FilesystemPolicyRepository


def test_filesystem_repository_loads_conjunctive_and_branched_policies() -> None:
    repo = FilesystemPolicyRepository()

    arthro = repo.get_document("PA-KNEE-ARTHRO-001", "1.0.0")
    assert arthro.logic == "all_of"
    assert [item.id for item in arthro.criteria] == [
        "C1_symptoms",
        "C2_oa_severity",
        "C3_radiologic_confirmation",
        "C4_conservative_therapy",
    ]
    assert arthro.waivers[0].id == "W1_locked_knee"

    knee_mri = repo.get_document("PA-KNEE-MRI-001", "1.0.0")
    assert knee_mri.logic == "any_of"
    criterion_ids = {item.id for item in knee_mri.criteria}
    assert "B1_C1_persistent_symptoms" in criterion_ids
    assert "B3_preoperative_planning" in criterion_ids
    assert "B4_postoperative_recurrence" in criterion_ids
    branch_ids = {item.id for item in knee_mri.branches}
    assert "B2_acute_trauma_with_effusion" in branch_ids

    versions = repo.list_versions_for("HUMANA-COMMERCIAL-01", "knee_arthroscopy")
    assert len(versions) == 1
    assert versions[0].policy_id == "PA-KNEE-ARTHRO-001"
    assert versions[0].effective_from.isoformat() == "2013-06-01"
