import sqlite3

import pytest
from pydantic import ValidationError

from banking_service import BankingService
from database import Database
from models import ApplicationInput


@pytest.fixture
def setup_service(tmp_path):
    database = Database(tmp_path / "test.sqlite3")
    service = BankingService(database, "demo-001", 12.5, 40)
    state = {}
    service.set_pending_application(
        state,
        customer_id="demo-001",
        loan_amount=500_000,
        tenure_months=36,
        calculated_emi=16_733.74,
        interest_rate=12.5,
        eligible=True,
        current_turn=1,
    )
    values = ApplicationInput(
        customer_id="demo-001",
        loan_amount=500_000,
        tenure_months=36,
        calculated_emi=16_733.74,
        interest_rate=12.5,
        preliminarily_eligible=True,
        customer_confirmation="yes i confirm submission",
        application_details={"purpose": "Personal loan"},
    )
    return service, database, state, values


def test_unauthorized_account_retrieval(setup_service):
    service, _, _, _ = setup_service

    with pytest.raises(PermissionError, match="Authenticate"):
        service.get_account_details("demo-001", authenticated=False)


def test_authenticated_account_retrieval_returns_masked_data(setup_service):
    service, _, _, _ = setup_service

    account = service.get_account_details("demo-001", authenticated=True)

    assert account["masked_account_number"] == "XXXXXX4821"
    assert account["masked_mobile_number"] == "+91-98XXXXXX42"
    assert "customer_id" not in account


def test_missing_application_details_are_rejected():
    with pytest.raises(ValidationError, match="Application purpose is required"):
        ApplicationInput(
            customer_id="demo-001",
            loan_amount=500_000,
            tenure_months=36,
            calculated_emi=16_733.74,
            interest_rate=12.5,
            preliminarily_eligible=True,
            customer_confirmation="yes i confirm submission",
            application_details={},
        )


def test_application_without_confirmation_is_not_submitted(setup_service):
    service, _, state, values = setup_service

    with pytest.raises(PermissionError, match="Explicit confirmation"):
        service.submit_application(
            values,
            authenticated=True,
            actual_user_message="Yes",
            current_turn=2,
            session_state=state,
        )


def test_stale_terms_invalidate_confirmation(setup_service):
    service, _, state, values = setup_service
    changed_terms = values.model_copy(update={"loan_amount": 600_000})

    with pytest.raises(PermissionError, match="terms changed"):
        service.submit_application(
            changed_terms,
            authenticated=True,
            actual_user_message="Yes, I confirm submission",
            current_turn=2,
            session_state=state,
        )
    assert "pending_application" not in state


def test_confirmation_after_an_intervening_turn_is_rejected(setup_service):
    service, _, state, values = setup_service

    with pytest.raises(PermissionError, match="next turn"):
        service.submit_application(
            values,
            authenticated=True,
            actual_user_message="Yes, I confirm submission",
            current_turn=3,
            session_state=state,
        )
    assert "pending_application" not in state


def test_valid_confirmation_records_application(setup_service):
    service, database, state, values = setup_service

    result = service.submit_application(
        values,
        authenticated=True,
        actual_user_message="Yes, I confirm submission",
        current_turn=2,
        session_state=state,
    )

    assert result["reference"].startswith("DEMO-")
    assert result["status"] == "submitted successfully (demo record)"
    assert state["application_status"] == "Submitted successfully (demo record)"
    assert "not a real bank" in result["message"]
    assert "pending_application" not in state
    with sqlite3.connect(database.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM loan_applications").fetchone()[0] == 1


def test_labeled_confirmation_and_purpose_records_application(setup_service):
    service, _, state, values = setup_service

    result = service.submit_application(
        values,
        authenticated=True,
        actual_user_message="Loan purpose: home renovation. Explicit Confirmation: yes",
        current_turn=2,
        session_state=state,
    )

    assert result["status"] == "submitted successfully (demo record)"


def test_duplicate_submission_does_not_create_another_record(setup_service):
    service, database, state, values = setup_service
    first = service.submit_application(
        values,
        authenticated=True,
        actual_user_message="Yes, I confirm submission",
        current_turn=2,
        session_state=state,
    )
    service.set_pending_application(
        state,
        customer_id="demo-001",
        loan_amount=500_000,
        tenure_months=36,
        calculated_emi=16_733.74,
        interest_rate=12.5,
        eligible=True,
        current_turn=3,
    )
    duplicate = service.submit_application(
        values,
        authenticated=True,
        actual_user_message="Yes, I confirm submission",
        current_turn=4,
        session_state=state,
    )

    assert duplicate["reference"] == first["reference"]
    assert "already recorded" in duplicate["message"]
    assert state["application_status"] == "Submitted successfully (demo record)"
    with sqlite3.connect(database.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM loan_applications").fetchone()[0] == 1