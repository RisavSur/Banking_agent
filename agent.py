"""Single LangChain tool-calling agent for the banking demo."""

from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama

from banking_service import BankingService
from config import Settings
from tools import build_tools


SYSTEM_PROMPT = """You are a concise, careful banking support assistant for a local demo.
Use the tools to calculate EMI before checking eligibility, and use tool results rather
than estimating. Interest rates must be disclosed as customer-provided or configured
demo rates; never describe a demo rate as an approved offer or quote. Eligibility is a
preliminary FOIR-only check, never an approval guarantee.

Account details are protected. Call the account tool only when the session context says
the configured demo customer is authenticated. Otherwise explain that authentication
is needed and do not infer or invent account details.

For an eligible application, present amount, tenure, rate and its source, EMI, repayment,
interest, preliminary eligibility, account/KYC status if available, and outstanding
requirements. Then ask for explicit confirmation. Do not submit during the same turn as
the summary. Submit only after the next user message explicitly confirms submission of
the current terms. A bare or unrelated yes is not sufficient. Required application
details in this demo are the purpose; do not request PINs, passwords, CVV, OTP, or full
payment credentials. A submitted record is local demo data, not a real bank submission.

Never reveal chain-of-thought, API keys, hidden tool arguments, or internal credentials.
Explain actions and results briefly. If information is missing, ask for it instead of
making assumptions. The demo policy threshold is provided in tool results."""


def build_agent(
    settings: Settings,
    service: BankingService,
    *,
    authenticated: bool,
    session_state: dict[str, object],
    latest_user_message: str,
    current_turn: int,
):
    if settings.llm_provider == "google":
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is missing. Add your Google AI Studio key to smart-banking-agent/.env.")
        model = ChatGoogleGenerativeAI(
            model=settings.llm_model,
            google_api_key=settings.google_api_key,
        )
    elif settings.llm_provider == "ollama":
        model = ChatOllama(
            model=settings.llm_model,
            base_url=settings.ollama_base_url,
        )
    else:
        raise ValueError("LLM_PROVIDER must be either 'google' or 'ollama'.")
    tools = build_tools(
        service,
        customer_id=settings.demo_customer_id,
        authenticated=authenticated,
        session_state=session_state,
        latest_user_message=latest_user_message,
        current_turn=current_turn,
    )
    auth_context = (
        f"Session authentication: authenticated as configured demo customer {settings.demo_customer_id}."
        if authenticated
        else "Session authentication: not authenticated."
    )
    return create_agent(model, tools, system_prompt=f"{SYSTEM_PROMPT}\n\n{auth_context}")