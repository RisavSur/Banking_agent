from dataclasses import replace

from agent import build_agent
from banking_service import BankingService
from config import load_settings
from database import Database


def test_ollama_agent_constructs_without_google_api_key(tmp_path):
    settings = replace(
        load_settings(),
        google_api_key="",
        llm_provider="ollama",
        llm_model="qwen3:8b",
        ollama_base_url="http://localhost:11434",
    )
    service = BankingService(Database(tmp_path / "ollama-test.sqlite3"), "demo-001", 12.5, 40)

    agent = build_agent(
        settings,
        service,
        authenticated=False,
        session_state={},
        latest_user_message="",
        current_turn=0,
    )

    assert type(agent).__name__ == "CompiledStateGraph"