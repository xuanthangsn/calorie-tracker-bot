"""Minimal configuration from environment (.env supported)."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

# LLM workspace root: path or directory name from env (see agent_system_design.md).
# Relative values are resolved under the process current working directory.
MEMORY_ROOT: str = (os.getenv("MEMORY_ROOT") or "").strip()