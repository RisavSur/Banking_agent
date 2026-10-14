"""Environment-backed settings for the local banking demo."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")


def _optional_float(name: str) -> float | None:
    value = os.getenv(name, "").strip()
    return float(value) if value else None


@dataclass(frozen=True)
class Settings:
    google_api_key: str
    llm_provider: str
    llm_model: str
    ollama_base_url: str
    database_path: Path
    demo_interest_rate: float | None
    max_foir_percent: float
    demo_customer_id: str


def load_settings() -> Settings:
    database_path = Path(os.getenv("DATABASE_PATH", "banking_demo.sqlite3"))
    if not database_path.is_absolute():
        database_path = PROJECT_DIR / database_path

    return Settings(
        google_api_key=os.getenv("GOOGLE_API_KEY", "").strip(),
        llm_provider=os.getenv("LLM_PROVIDER", "google").strip().lower(),
        llm_model=os.getenv("LLM_MODEL", "gemini-2.5-flash").strip(),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip(),
        database_path=database_path,
        demo_interest_rate=_optional_float("DEMO_INTEREST_RATE"),
        max_foir_percent=float(os.getenv("MAX_FOIR_PERCENT", "40")),
        demo_customer_id=os.getenv("DEMO_CUSTOMER_ID", "demo-customer-001").strip(),
    )