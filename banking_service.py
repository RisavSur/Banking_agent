"""Deterministic banking calculations, authorization, and application rules."""

from datetime import datetime, timezone
import hashlib
import json
import re
import secrets

from database import Database
from models import ApplicationInput, EligibilityInput, EmiInput


class BankingService:
    def __init__(
        self,
        database: Database,
        demo_customer_id: str,
        demo_interest_rate: float | None,
        max_foir_percent: float,
    ):
        self.database = database
        self.demo_customer_id = demo_customer_id
        self.demo_interest_rate = demo_interest_rate
        self.max_foir_percent = max_foir_percent
        self.database.initialize(demo_customer_id)

    def calculate_emi(self, values: EmiInput) -> dict[str, float | int | str]:
        rate = values.annual_interest_rate
        rate_source = "customer-provided rate"
        if rate is None:
            rate = self.demo_interest_rate
            rate_source = "configured demo rate"
        if rate is None:
            raise ValueError(
                "An interest rate is required. No demo rate is configured; please provide a rate."
            )

        monthly_rate = rate / 1200
        if monthly_rate == 0:
            monthly_emi = values.principal / values.tenure_months
        else:
            factor = (1 + monthly_rate) ** values.tenure_months
            monthly_emi = values.principal * monthly_rate * factor / (factor - 1)
        total_repayment = monthly_emi * values.tenure_months
        return {
            "monthly_emi": round(monthly_emi, 2),
            "total_repayment": round(total_repayment, 2),
            "total_interest": round(total_repayment - values.principal, 2),
            "interest_rate_percent": rate,
            "interest_rate_source": rate_source,
            "tenure_months": values.tenure_months,
        }

    def check_eligibility(self, values: EligibilityInput) -> dict[str, object]:
        total_emi = values.existing_monthly_emi + values.proposed_monthly_emi
        foir = total_emi / values.monthly_salary * 100
        max_emi = values.monthly_salary * values.max_foir_percent / 100
        eligible = total_emi <= max_emi
        reasons = (
            ["Total monthly EMI is within the configured FOIR limit."]
            if eligible
            else ["Total monthly EMI exceeds the configured FOIR limit."]
        )
        result = {
            "result": "preliminarily eligible" if eligible else "not eligible",
            "eligible": eligible,
            "monthly_income": values.monthly_salary,
            "existing_emi": values.existing_monthly_emi,
            "proposed_emi": values.proposed_monthly_emi,
            "total_monthly_emi": round(total_emi, 2),
            "foir_percent": round(foir, 2),
            "max_permitted_emi": round(max_emi, 2),
            "foir_threshold_percent": values.max_foir_percent,
            "reasons": reasons,
            "additional_verification_requirements": [
                "Credit score and employment stability may be reviewed.",
                "KYC, account verification, and the bank's actual lending policy apply.",
                "Passing this demo affordability check does not guarantee loan approval.",
            ],
        }
        return result

    def get_account_details(self, customer_id: str | None, authenticated: bool) -> dict[str, object]:
        if not authenticated or customer_id != self.demo_customer_id:
            raise PermissionError("Authenticate the configured demo customer before account access.")
        account = self.database.get_account(customer_id)
        if account is None:
            raise LookupError("No demo account is available for this authenticated customer.")
        return account

    @staticmethod
    def terms_fingerprint(
        customer_id: str, loan_amount: float, tenure_months: int, calculated_emi: float, interest_rate: float
    ) -> str:
        terms = {
            "customer_id": customer_id,
            "loan_amount": round(float(loan_amount), 2),
            "tenure_months": int(tenure_months),
            "calculated_emi": round(float(calculated_emi), 2),
            "interest_rate": round(float(interest_rate), 6),
        }
        return hashlib.sha256(json.dumps(terms, sort_keys=True).encode()).hexdigest()

    def set_pending_application(
        self,
        state: dict[str, object],
        *,
        customer_id: str,
        loan_amount: float,
        tenure_months: int,
        calculated_emi: float,
        interest_rate: float,
        eligible: bool,
        current_turn: int,
    ) -> None:
        if not eligible:
            state.pop("pending_application", None)
            state["application_status"] = "Rejected by demo eligibility rules"
            return
        state["pending_application"] = {
            "customer_id": customer_id,
            "loan_amount": loan_amount,
            "tenure_months": tenure_months,
            "calculated_emi": calculated_emi,
            "interest_rate": interest_rate,
            "eligible": True,
            "fingerprint": self.terms_fingerprint(
                customer_id, loan_amount, tenure_months, calculated_emi, interest_rate
            ),
            "created_turn": current_turn,
        }
        state["application_status"] = "Awaiting customer confirmation"

    @staticmethod
    def _is_explicit_confirmation(message: str) -> bool:
        normalized = re.sub(r"[^a-z ]", " ", message.lower())
        normalized = " ".join(normalized.split())
        accepted = {
            "yes i confirm submission",
            "yes i confirm that i want you to submit this loan application",
            "i confirm submission",
            "i confirm that you may submit this loan application",
            "yes please submit this loan application i confirm",
        }
        labeled_confirmation = (
            "explicit confirmation yes" in normalized
            and "loan purpose" in normalized
            and not any(
                phrase in normalized
                for phrase in ("no explicit confirmation", "do not submit", "cancel submission")
            )
        )
        return normalized in accepted or labeled_confirmation

    def submit_application(
        self,
        values: ApplicationInput,
        *,
        authenticated: bool,
        actual_user_message: str,
        current_turn: int,
        session_state: dict[str, object],
    ) -> dict[str, object]:
        if not authenticated or values.customer_id != self.demo_customer_id:
            session_state["application_status"] = "Failed: authentication required"
            raise PermissionError("Authentication is required to submit an application.")
        if not values.preliminarily_eligible:
            session_state["application_status"] = "Rejected by demo eligibility rules"
            return {"status": "rejected by demo eligibility rules", "submitted": False}

        pending = session_state.get("pending_application")
        if not isinstance(pending, dict):
            session_state["application_status"] = "Failed: no current application awaits confirmation"
            raise PermissionError("No current eligible application is awaiting confirmation.")
        if current_turn != int(pending["created_turn"]) + 1:
            session_state.pop("pending_application", None)
            session_state["application_status"] = "Failed: confirmation was not received on the next turn"
            raise PermissionError("Confirmation must arrive on the next turn after the application summary.")
        fingerprint = self.terms_fingerprint(
            values.customer_id,
            values.loan_amount,
            values.tenure_months,
            values.calculated_emi,
            values.interest_rate,
        )
        if fingerprint != pending["fingerprint"]:
            session_state.pop("pending_application", None)
            session_state["application_status"] = "Failed: loan terms changed"
            raise PermissionError("Loan terms changed. Recalculate and review a new summary before confirming.")
        if not pending.get("eligible"):
            session_state["application_status"] = "Rejected by demo eligibility rules"
            raise PermissionError("This application has not passed the demo eligibility check.")
        if not self._is_explicit_confirmation(actual_user_message):
            session_state["application_status"] = "Failed: explicit customer confirmation required"
            raise PermissionError("Explicit confirmation of the current loan application is required.")
        if not values.application_details.get("purpose", "").strip():
            session_state["application_status"] = "Failed: application purpose is missing"
            raise ValueError("Application purpose is required.")

        submission_key = fingerprint
        existing = self.database.get_application_by_key(submission_key)
        if existing:
            session_state.pop("pending_application", None)
            session_state["application_status"] = "Submitted successfully (demo record)"
            return {
                "status": existing["status"],
                "reference": existing["reference"],
                "submitted_at": existing["submitted_at"],
                "message": "This application was already recorded; no duplicate was created.",
            }

        application = {
            "reference": f"DEMO-{secrets.token_hex(4).upper()}",
            "customer_id": values.customer_id,
            "loan_amount": values.loan_amount,
            "tenure_months": values.tenure_months,
            "calculated_emi": values.calculated_emi,
            "interest_rate": values.interest_rate,
            "purpose": values.application_details["purpose"].strip(),
            "submitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": "submitted successfully (demo record)",
            "submission_key": submission_key,
        }
        try:
            self.database.insert_application(application)
        except Exception:
            duplicate = self.database.get_application_by_key(submission_key)
            if duplicate is None:
                raise
            application = duplicate
        session_state.pop("pending_application", None)
        session_state["application_status"] = "Submitted successfully (demo record)"
        return {
            "status": application["status"],
            "reference": application["reference"],
            "submitted_at": application["submitted_at"],
            "message": "Recorded in the local demo database; this is not a real bank submission or approval.",
        }