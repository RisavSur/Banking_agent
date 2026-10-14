import pytest
from pydantic import ValidationError

from banking_service import BankingService
from database import Database
from models import EmiInput


@pytest.fixture
def service(tmp_path):
    return BankingService(Database(tmp_path / "test.sqlite3"), "demo-001", 12.5, 40)


def test_positive_interest_reducing_balance_emi(service):
    result = service.calculate_emi(EmiInput(principal=500_000, tenure_months=36))

    assert result["monthly_emi"] == pytest.approx(16_726.81, abs=0.01)
    assert result["total_repayment"] == pytest.approx(602_165.26, abs=0.02)
    assert result["total_interest"] == pytest.approx(102_165.26, abs=0.02)
    assert result["interest_rate_percent"] == 12.5
    assert result["interest_rate_source"] == "configured demo rate"


def test_zero_interest_emi(service):
    result = service.calculate_emi(
        EmiInput(principal=1200, annual_interest_rate=0, tenure_months=12)
    )

    assert result["monthly_emi"] == 100
    assert result["total_interest"] == 0


@pytest.mark.parametrize(
    "values",
    [
        {"principal": 0, "tenure_months": 12},
        {"principal": -1, "tenure_months": 12},
        {"principal": 1000, "tenure_months": 0},
        {"principal": 1000, "tenure_months": 601},
    ],
)
def test_invalid_amounts_and_tenures_are_rejected(values):
    with pytest.raises(ValidationError):
        EmiInput(**values)


def test_missing_interest_rate_is_not_silently_assumed(tmp_path):
    service = BankingService(Database(tmp_path / "no-rate.sqlite3"), "demo-001", None, 40)

    with pytest.raises(ValueError, match="interest rate is required"):
        service.calculate_emi(EmiInput(principal=500_000, tenure_months=36))