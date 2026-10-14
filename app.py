"""Streamlit chat UI for the synthetic Smart Banking Support Agent."""

from dataclasses import replace
import json
from urllib.error import URLError
from urllib.request import urlopen

import streamlit as st

from agent import build_agent
from banking_service import BankingService
from config import load_settings
from database import Database


GEMINI_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash",
]
PROVIDER_LABELS = {
    "Ollama (local)": "ollama",
    "Google Gemini (API)": "google",
}


def get_ollama_models(base_url: str) -> list[str]:
    try:
        with urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=1.5) as response:
            models = json.load(response).get("models", [])
        return sorted(model["name"] for model in models if model.get("name"))
    except (OSError, URLError, ValueError, TimeoutError):
        return []


st.set_page_config(page_title="Smart Banking Support", page_icon="₹", layout="centered")
st.title("Smart Banking Support")
st.caption("Local demo assistant. No real bank systems or transactions are connected.")

settings = load_settings()
service = BankingService(
    Database(settings.database_path),
    settings.demo_customer_id,
    settings.demo_interest_rate,
    settings.max_foir_percent,
)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "turn" not in st.session_state:
    st.session_state.turn = 0
if "pending_application" not in st.session_state:
    st.session_state.pending_application = None
if "application_status" not in st.session_state:
    st.session_state.application_status = "Not started"

with st.sidebar:
    st.subheader("Language model")
    provider_options = list(PROVIDER_LABELS)
    default_provider_label = next(
        (label for label, provider in PROVIDER_LABELS.items() if provider == settings.llm_provider),
        "Google Gemini (API)",
    )
    if "provider_choice" not in st.session_state:
        st.session_state.provider_choice = default_provider_label
    provider_label = st.segmented_control(
        "Provider",
        options=provider_options,
        key="provider_choice",
        label_visibility="collapsed",
    )
    selected_provider = PROVIDER_LABELS[provider_label or default_provider_label]

    if selected_provider == "ollama":
        installed_models = get_ollama_models(settings.ollama_base_url)
        model_options = list(installed_models)
        if settings.llm_model not in model_options:
            model_options.insert(0, settings.llm_model)
        if not model_options:
            model_options = ["qwen3:8b"]
            st.warning("Ollama is unreachable or has no downloaded models.")
        model_key = "ollama_model_choice"
        model_default = settings.llm_model if settings.llm_model in model_options else model_options[0]
    else:
        model_options = GEMINI_MODELS
        model_key = "gemini_model_choice"
        model_default = settings.llm_model if settings.llm_model in model_options else GEMINI_MODELS[0]

    if st.session_state.get(model_key) not in model_options:
        st.session_state[model_key] = model_default
    selected_model = st.selectbox("Model", options=model_options, key=model_key)
    active_settings = replace(
        settings,
        llm_provider=selected_provider,
        llm_model=selected_model,
    )
    st.caption(f"Active: {provider_label} / {selected_model}")
    if selected_provider == "ollama":
        st.caption(f"Endpoint: {settings.ollama_base_url}")
    elif not settings.google_api_key:
        st.warning("Add GOOGLE_API_KEY to .env to use Gemini.")

    st.subheader("Demo customer")
    st.write("Identity:", settings.demo_customer_id)
    if st.session_state.authenticated:
        st.success("Authenticated for this session")
        if st.button("Sign out", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.pending_application = None
            st.session_state.application_status = "Not started"
            st.rerun()
    elif st.button("Authenticate demo user", use_container_width=True):
        st.session_state.authenticated = True
        st.rerun()
    st.caption("Authentication is a local demo toggle, not production identity verification.")
    rate_text = (
        f"{settings.demo_interest_rate:.2f}% configured demo rate"
        if settings.demo_interest_rate is not None
        else "No demo rate configured"
    )
    st.write("Rate policy:", rate_text)
    st.write("FOIR limit:", f"{settings.max_foir_percent:.1f}%")
    st.write("Application status:", st.session_state.application_status)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask about a loan or your demo account"):
    st.session_state.turn += 1
    current_turn = st.session_state.turn
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            agent = build_agent(
                active_settings,
                service,
                authenticated=st.session_state.authenticated,
                session_state=st.session_state,
                latest_user_message=prompt,
                current_turn=current_turn,
            )
            response = agent.invoke(
                {
                    "messages": [
                        {"role": message["role"], "content": message["content"]}
                        for message in st.session_state.messages
                    ]
                }
            )
            answer = response["messages"][-1].content
            if isinstance(answer, list):
                answer = "\n".join(
                    item.get("text", "") for item in answer if isinstance(item, dict)
                )
            st.markdown(answer)
        except (PermissionError, ValueError, LookupError) as error:
            answer = f"This action was not completed: {error} No application was submitted."
            st.warning(answer)
        except Exception as error:
            error_text = str(error).lower()
            if "resource_exhausted" in error_text or ("429" in error_text and "quota" in error_text):
                answer = (
                    "Gemini's free-tier request quota is exhausted for this model. "
                    "Wait for the quota reset or check Google AI Studio's usage limits, "
                    "then retry. No application was submitted."
                )
                st.warning(answer)
            else:
                answer = (
                    "I could not complete that request. Check the model/API configuration "
                    "and try again. No application was submitted unless a reference number is shown."
                )
                st.error(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})