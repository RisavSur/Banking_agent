import pytest

from banking_service import BankingService
from database import Database
from models import EligibilityInput


@pytest.fixture
def service(tmp_path):
    return BankingService(Database(tmp_path / "test.sqlite3"), "demo-001", 12.5, 40)


def test_foir_calculation_and_preliminary_eligibility(service):
    result = service.check_eligibility(
        EligibilityInput(
            monthly_salary=60_000,
            existing_monthly_emi=5_000,
            proposed_monthly_emi=16_726.81,
            requested_loan_amount=500_000,
            tenure_months=36,
            max_foir_percent=40,
        )
    )

    assert result["eligible"] is True
    assert result["total_monthly_emi"] == 21_726.81
    assert result["foir_percent"] == pytest.approx(36.21, abs=0.01)
    assert result["max_permitted_emi"] == 24_000
    assert "does not guarantee" in result["additional_verification_requirements"][-1]


def test_foir_rejection(service):
    result = service.check_eligibility(
        EligibilityInput(
            monthly_salary=30_000,
            existing_monthly_emi=8_000,
            proposed_monthly_emi=8_500,
            requested_loan_amount=500_000,
            tenure_months=36,
            max_foir_percent=40,
        )
    )

    assert result["eligible"] is False
    assert result["foir_percent"] == 55
    assert "exceeds" in result["reasons"][0]