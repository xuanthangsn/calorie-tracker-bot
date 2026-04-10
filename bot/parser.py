"""Instructor + LLM intent parsing (structured Action)."""
from __future__ import annotations
import json
import instructor
import config
from action import Action


SYSTEM_PROMPT = 
"""You are a calorie tracking agent. Your ONLY job is to log meals, edit past logs.
You may ask clarification question if you want to clarify user's intention.
You should immediately refuse to answer if you are sure that the user's message or request is not related to your job.
You will be provided with a list of action to take in the Action schema.
Output ONLY valid JSON matching the Action schema."""

LLM_API_CLIENT = None

def get_LLM_api_client():
    if LLM_API_CLIENT is not None:
        return LLM_API_CLIENT
    LLM_API_CLIENT = instructor.from_provider("google/gemini-3-flash-preview")
    return LLM_API_CLIENT


def parse_user_message(user_text: str, compact_context: dict[str, Any]) -> Action:
    client = get_LLM_api_client()
    ctx_json = json.dumps(compact_context, ensure_ascii=False, default=str)
    user_block = f"Context (JSON):\n{ctx_json}\n\nUser message:\n{user_text}"

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
