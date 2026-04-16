"""Configuration from environment (.env supported)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_FILE = DATA_DIR / "calorie_data.json"

TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
# Chat ID for scheduled auto-reports (same as user DM chat_id for personal bot)
def _optional_int(env_name: str) -> int | None:
    raw = os.getenv(env_name)
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(str(raw).strip())
    except ValueError:
        return None


TELEGRAM_CHAT_ID: int | None = _optional_int("TELEGRAM_CHAT_ID")

OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY") or None
# google.genai (Gemini) — either name works
GEMINI_API_KEY: str | None = (
    os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or None
)
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

USDA_API_KEY: str | None = os.getenv("USDA_API_KEY") or None

# Timezone for reports / log dates (IANA name)
TZ_NAME: str = os.getenv("TZ", "UTC")
