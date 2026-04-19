"""Minimal configuration from environment (.env supported)."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")