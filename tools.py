"""LangChain tools bound to one authenticated Streamlit session."""

import json
import re

from langchain.tools import tool
from pydantic import BaseModel, Field

from banking_service import BankingService
from models import ApplicationInput, EligibilityInput, EmiInput


class EmiToolInput(BaseModel):
    principal: float = Field(gt=0, description="Loan principal in INR")
    tenure_months: int = Field(gt=0, le=600)


class EligibilityToolInput(BaseModel):
    monthly_salary: float = Field(gt=0)
    existing_monthly_emi: float = Field(ge=0)
    proposed_monthly_emi: float = Field(ge=0)
    requested_loan_amount: float = Field(gt=0)
    tenure_months: int = Field(gt=0, le=600)


class AccountToolInput(BaseModel):
    """No customer identifier is accepted from the model."""


def build_tools(
    service: BankingService,
    *,
    customer_id: str,
    authenticated: bool,
    session_state: dict[str, object],
    latest_user_message: str,
    current_turn: int,
) -> list:
    pending = session_state.get("pending_application")
    if isinstance(pending, dict) and (
        current_turn != int(pending["created_turn"]) + 1
        or not service._is_explicit_confirmation(latest_user_message)
    ):
        session_state.pop("pending_application", None)

    @tool("calculate_emi", args_schema=EmiToolInput)
    def calculate_emi(principal: float, tenure_months: int) -> str:
        """Calculate a reducing-balance EMI and total repayment in INR."""
        rate_match = re.search(
            r"(?:interest\s+rate|annual\s+rate|apr)\s*(?:is|of|:)?\s*"
            r"(\d+(?:\.\d+)?)\s*(?:%|percent)\b|"
            r"(\d+(?:\.\d+)?)\s*(?:%|percent)\s*"
            r"(?:per\s+annum|annual|p\.?a\.?|interest(?:\s+rate)?)\b",
            latest_user_message,
            flags=re.IGNORECASE,
        )
        explicit_rate = None
        if rate_match:
            explicit_rate = float(rate_match.group(1) or rate_match.group(2))
        result = service.calculate_emi(
            EmiInput(
                principal=principal,
                tenure_months=tenure_months,
                annual_interest_rate=explicit_rate,
            )
        )
        session_state["latest_emi"] = {
            "principal": principal,
            "tenure_months": tenure_months,
            **result,
        }
        return json.dumps(result)

    @tool("check_loan_eligibility", args_schema=EligibilityToolInput)
    def check_loan_eligibility(
        monthly_salary: float,
        existing_monthly_emi: float,
        proposed_monthly_emi: float,
        requested_loan_amount: float,
        tenure_months: int,
    ) -> str:
        """Check preliminary affordability using the configured FOIR policy."""
        calculated = session_state.get("latest_emi")
        if not isinstance(calculated, dict):
            raise ValueError("Calculate the proposed EMI first; eligibility uses the calculator result.")
        if (
            round(float(calculated["principal"]), 2) != round(requested_loan_amount, 2)
            or int(calculated["tenure_months"]) != tenure_months
            or round(float(calculated["monthly_emi"]), 2) != round(proposed_monthly_emi, 2)
        ):
            raise ValueError("Recalculate the EMI for the current loan amount and tenure before checking eligibility.")
        result = service.check_eligibility(
            EligibilityInput(
                monthly_salary=monthly_salary,
                existing_monthly_emi=existing_monthly_emi,
                proposed_monthly_emi=proposed_monthly_emi,
                requested_loan_amount=requested_loan_amount,
                tenure_months=tenure_months,
                max_foir_percent=service.max_foir_percent,
            )
        )
        if bool(result["eligible"]) and authenticated:
            service.set_pending_application(
                session_state,
                customer_id=customer_id,
                loan_amount=requested_loan_amount,
                tenure_months=tenure_months,
                calculated_emi=float(calculated["monthly_emi"]),
                interest_rate=float(calculated["interest_rate_percent"]),
                eligible=True,
                current_turn=current_turn,
            )
        elif not bool(result["eligible"]):
            service.set_pending_application(
                session_state,
                customer_id=customer_id,
                loan_amount=requested_loan_amount,
                tenure_months=tenure_months,
                calculated_emi=float(calculated["monthly_emi"]),
                interest_rate=float(calculated["interest_rate_percent"]),
                eligible=False,
                current_turn=current_turn,
            )
        else:
            session_state.pop("pending_application", None)
            session_state["application_status"] = "Not started"
        if not authenticated:
            result["application_note"] = (
                "Eligibility is only a preliminary calculation. Authenticate before preparing or submitting an application."
            )
        return json.dumps(result)

    @tool("get_account_details", args_schema=AccountToolInput)
    def get_account_details() -> str:
        """Retrieve minimum masked account details for the authenticated demo customer."""
        result = service.get_account_details(customer_id, authenticated)
        return json.dumps(result)

    @tool("submit_loan_application", args_schema=ApplicationInput)
    def submit_loan_application(
        customer_id: str,
        loan_amount: float,
        tenure_months: int,
        calculated_emi: float,
        interest_rate: float,
        preliminarily_eligible: bool,
        customer_confirmation: str,
        application_details: dict[str, str],
    ) -> str:
        """Submit a demo application only after fresh explicit confirmation of pending terms."""
        result = service.submit_application(
            ApplicationInput(
                customer_id=customer_id,
                loan_amount=loan_amount,
                tenure_months=tenure_months,
                calculated_emi=calculated_emi,
                interest_rate=interest_rate,
                preliminarily_eligible=preliminarily_eligible,
                customer_confirmation=customer_confirmation,
                application_details=application_details,
            ),
            authenticated=authenticated,
            actual_user_message=latest_user_message,
            current_turn=current_turn,
            session_state=session_state,
        )
        return json.dumps(result)

    return [calculate_emi, check_loan_eligibility, get_account_details, submit_loan_application]