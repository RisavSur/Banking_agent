import json

from banking_service import BankingService
from database import Database
from tools import build_tools


def test_calculate_emi_uses_demo_rate_not_model_supplied_rate(tmp_path):
    service = BankingService(Database(tmp_path / "tool.sqlite3"), "demo-001", 12.5, 40)
    calculate_emi = build_tools(
        service,
        customer_id="demo-001",
        authenticated=False,
        session_state={},
        latest_user_message="Calculate an EMI for 500000 INR over 36 months.",
        current_turn=1,
    )[0]

    result = json.loads(
        calculate_emi.invoke(
            {"principal": 500_000, "tenure_months": 36, "annual_interest_rate": 8.5}
        )
    )

    assert result["interest_rate_percent"] == 12.5
    assert result["interest_rate_source"] == "configured demo rate"


def test_calculate_emi_uses_rate_explicitly_stated_by_customer(tmp_path):
    service = BankingService(Database(tmp_path / "explicit-rate.sqlite3"), "demo-001", 12.5, 40)
    calculate_emi = build_tools(
        service,
        customer_id="demo-001",
        authenticated=False,
        session_state={},
        latest_user_message="Calculate using an interest rate of 10% per annum.",
        current_turn=1,
    )[0]

    result = json.loads(
        calculate_emi.invoke({"principal": 500_000, "tenure_months": 36})
    )

    assert result["interest_rate_percent"] == 10
    assert result["interest_rate_source"] == "customer-provided rate"