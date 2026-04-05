"""Instructor + LLM intent parsing (structured Action)."""
from __future__ import annotations

import json
from typing import Any, Literal, Optional

import instructor
from litellm import completion
from pydantic import BaseModel

import config

SYSTEM_PROMPT = """You are a calorie tracking agent. Your ONLY job is to log meals, edit past logs, set goals, or generate reports.
You may ask ONE clarification question if the input is ambiguous.
Never chat, never give advice, never be friendly.
Output ONLY valid JSON matching the Action schema."""

LLM_API_CLIENT = None

def get_LLM_api_client():
    if LLM_API_CLIENT is not None:
        return LLM_API_CLIENT
    LLM_API_CLIENT = instructor.from_provider("google/gemini-3-flash-preview")
    return LLM_API_CLIENT

class MealItem(BaseModel):
    food: str
    quantity: str
    calories: Optional[int] = None


class Action(BaseModel):
    action: Literal[
        "log_meal",
        "edit_meal",
        "delete_meal",
        "set_goal",
        "get_report",
        "ask_clarification",
        "refuse",
    ]
    data: Optional[dict[str, Any]] = None
    target_meal_id: Optional[int] = None
    clarification_question: Optional[str] = None


def _litellm_kwargs() -> dict[str, Any]:
    kw: dict[str, Any] = {}
    m = config.LLM_MODEL.lower()
    if m.startswith("ollama") or "ollama" in m:
        kw["api_base"] = config.OLLAMA_BASE_URL
    return kw


def get_instructor_client():
    return instructor.from_litellm(completion)


def parse_user_message(user_text: str, compact_context: dict[str, Any]) -> Action:
    client = get_LLM_api_client()
    ctx_json = json.dumps(compact_context, ensure_ascii=False, default=str)
    user_block = f"Context (JSON):\n{ctx_json}\n\nUser message:\n{user_text}"

    kwargs = _litellm_kwargs()
    # if config.OPENAI_API_KEY:
    #     import os

    #     os.environ.setdefault("OPENAI_API_KEY", config.OPENAI_API_KEY)

    # resp = client.chat.completions.create(
    #     model=config.LLM_MODEL,
    #     response_model=Action,
    #     messages=[
    #         {"role": "system", "content": SYSTEM_PROMPT},
    #         {"role": "user", "content": user_block},
    #     ],
    #     max_tokens=800,
    #     temperature=0,
    #     api_key=(config.OPENAI_API_KEY if config.OPENAI_API_KEY else None),
    #     **kwargs,
    # )

    resp = client.create(
        response_model=Action,
        messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_block},
            ]
    )

    llm_request_str = f"""
    System Prompt: {SYSTEM_PROMPT}
    User Message: {user_block}
    """

    return resp, llm_request_str
