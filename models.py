"""Validated input schemas shared by banking services and agent tools."""

from pydantic import BaseModel, Field, field_validator


class EmiInput(BaseModel):
    principal: float = Field(gt=0, description="Loan principal in INR")
    annual_interest_rate: float | None = Field(
        default=None, ge=0, description="Annual nominal interest rate in percent"
    )
    tenure_months: int = Field(gt=0, le=600)


class EligibilityInput(BaseModel):
    monthly_salary: float = Field(gt=0)
    existing_monthly_emi: float = Field(ge=0)
    proposed_monthly_emi: float = Field(ge=0)
    requested_loan_amount: float = Field(gt=0)
    tenure_months: int = Field(gt=0, le=600)
    max_foir_percent: float = Field(gt=0, le=100)


class ApplicationInput(BaseModel):
    customer_id: str = Field(min_length=1)
    loan_amount: float = Field(gt=0)
    tenure_months: int = Field(gt=0, le=600)
    calculated_emi: float = Field(gt=0)
    interest_rate: float = Field(ge=0)
    preliminarily_eligible: bool
    customer_confirmation: str = Field(min_length=1)
    application_details: dict[str, str]

    @field_validator("application_details")
    @classmethod
    def require_purpose(cls, details: dict[str, str]) -> dict[str, str]:
        if not details.get("purpose", "").strip():
            raise ValueError("Application purpose is required")
        return details