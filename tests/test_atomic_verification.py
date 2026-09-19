from datetime import date

from src.atomic_verification import PlaceholderAtomicVerifier
from src.case_loading.models import (
    Member,
    PriorAuthorizationRequest,
    RequestedService,
)
from src.enums import AtomicLabel
from src.requirement_models.models import AtomicSubRequirement


def test_placeholder_verifier_returns_stable_schema() -> None:
    verifier = PlaceholderAtomicVerifier()
    output = verifier.verify(
        AtomicSubRequirement(
            criterion_id="C4",
            sub_requirement_id="C4.3",
            text="Physical therapy was supervised",
        ),
        notes=(),
        pa_request=PriorAuthorizationRequest(
            submitted_date=date(2014, 4, 16),
            member=Member(
                name="Test",
                member_id="X",
                dob=None,
                sex=None,
                plan=None,
                plan_id="PLAN-A",
            ),
            requested_service=RequestedService(
                description="svc",
                service_key="knee_arthroscopy",
            ),
        ),
    )
    assert output.output_label is AtomicLabel.NOT_PROVEN
    assert output.criterion_id == "C4"
    assert output.sub_requirement_id == "C4.3"
    assert output.notes == ()
    assert "NOT_PROVEN" in output.rationale
