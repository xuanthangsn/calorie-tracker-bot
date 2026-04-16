"""Gemini native function calling: one tool per action, Pydantic validation.

Requires the **google-genai** PyPI package (`pip install google-genai`), which provides
`from google import genai`. This is the current Google Gen AI SDK — not the older
`google-generativeai` package (`import google.generativeai as genai`).

If you see ``ModuleNotFoundError: No module named 'google'``, install deps in the same
Python you use to run the app (e.g. ``pip install -r requirements.txt`` or use ``.venv``).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Type

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

import config
from bot.action import (
    Action,
    AskClarificationAction,
    DeleteMealAction,
    EditMealAction,
    GetReportAction,
    LogMealAction,
    MealItem,
    RefuseAction,
    SetGoalAction,
)
from utils.gemini_schema import pydantic_model_to_gemini_parameters

log = logging.getLogger(__name__)

__all__ = ["Action", "MealItem", "parse_user_message", "get_tool_function_declarations"]


SYSTEM_PROMPT = """You are a calorie tracking agent. You MUST respond by calling exactly one tool.
Use tools to: log meals, edit/delete logs by id, set daily/weekly/monthly calorie goals,
or request daily/weekly/monthly reports.
If the user is ambiguous, call ask_clarification with one short question.
If the message is clearly not about calories or goals, call refuse."""


# Tool name -> Pydantic model (parameters = model fields)
# _TOOL_MODELS: dict[str, Type[BaseModel]] = {
#     "log_meal": LogMealAction,
#     "edit_meal": EditMealAction,
#     "delete_meal": DeleteMealAction,
#     "set_goal": SetGoalAction,
#     "get_report": GetReportAction,
#     "ask_clarification": AskClarificationAction,
#     "refuse": RefuseAction,
# }


_TOOL_MODELS: dict[str, Type[BaseModel]] = {
    "log_meal": LogMealAction,
    # "edit_meal": EditMealAction,
    # "delete_meal": DeleteMealAction,
    # "set_goal": SetGoalAction,
    # "get_report": GetReportAction,
    # "ask_clarification": AskClarificationAction,
    # "refuse": RefuseAction,
}


TOOL_DESCRIPTIONS: dict[str, str] = {
    "log_meal": "Log a new meal with food lines and meal type (breakfast/lunch/dinner/snack/other).",
    "edit_meal": "Change an existing log by id (meal type, date, and/or food lines).",
    "delete_meal": "Delete a log entry by id.",
    "set_goal": "Set daily and/or weekly and/or monthly calorie goals (kcal).",
    "get_report": "Request a daily, weekly, or monthly calorie report.",
    "ask_clarification": "Ask one short clarifying question when the request is ambiguous.",
    "refuse": "Use when the message is off-topic or not about calorie tracking.",
}


def _build_function_declarations() -> list[types.FunctionDeclaration]:
    out: list[types.FunctionDeclaration] = []
    for name, model_cls in _TOOL_MODELS.items():
        params = pydantic_model_to_gemini_parameters(model_cls)
        out.append(
            types.FunctionDeclaration(
                name=name,
                description=TOOL_DESCRIPTIONS.get(name, name),
                parameters=params,
            )
        )
    return out


_FUNCTION_DECLARATIONS: list[types.FunctionDeclaration] | None = None


def _function_declarations() -> list[types.FunctionDeclaration]:
    global _FUNCTION_DECLARATIONS
    if _FUNCTION_DECLARATIONS is None:
        _FUNCTION_DECLARATIONS = _build_function_declarations()
    return _FUNCTION_DECLARATIONS


def get_tool_function_declarations() -> list[types.FunctionDeclaration]:
    """All tool `FunctionDeclaration` objects (for tests / debugging)."""
    return _function_declarations()


_GENAI_CLIENT: genai.Client | None = None


def get_genai_client() -> genai.Client:
    global _GENAI_CLIENT
    if _GENAI_CLIENT is None:
        if not config.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY or GOOGLE_API_KEY must be set for Gemini tool calling."
            )
        _GENAI_CLIENT = genai.Client(api_key=config.GEMINI_API_KEY)
    return _GENAI_CLIENT


def _args_to_plain_dict(args: Any) -> dict[str, Any]:
    if args is None:
        return {}
    if isinstance(args, dict):
        return {k: _args_to_plain_dict(v) if isinstance(v, dict) else v for k, v in args.items()}
    if hasattr(args, "items"):
        return dict(args)
    return {}


def _extract_function_call(
    resp: types.GenerateContentResponse,
) -> tuple[str, dict[str, Any]]:
    if not resp.candidates:
        raise ValueError("No candidates in model response")

    cand = resp.candidates[0]
    fr = getattr(cand, "finish_reason", None)
    if fr is not None:
        bad = (
            types.FinishReason.SAFETY,
            types.FinishReason.BLOCKLIST,
            types.FinishReason.PROHIBITED_CONTENT,
            types.FinishReason.SPII,
        )
        if fr in bad:
            raise ValueError(f"Model response blocked (finish_reason={fr})")

    content = cand.content
    if not content or not content.parts:
        raise ValueError("Empty model content")

    for part in content.parts:
        fc = getattr(part, "function_call", None)
        if fc is None:
            continue
        name = fc.name
        if not name:
            continue
        raw = _args_to_plain_dict(getattr(fc, "args", None))
        return str(name), raw

    raise ValueError("Model did not call any tool (expected exactly one function call)")


def parse_user_message(user_text: str, compact_context: dict[str, Any]) -> tuple[Action, str]:
    client = get_genai_client()
    ctx_json = json.dumps(compact_context, ensure_ascii=False, default=str)
    user_block = f"Context (JSON):\n{ctx_json}\n\nUser message:\n{user_text}"

    tool_names = list(_TOOL_MODELS.keys())
    gen_cfg = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[types.Tool(function_declarations=_function_declarations())],
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(
                mode=types.FunctionCallingConfigMode.ANY,
                allowed_function_names=tool_names,
            )
        ),
        temperature=0.0,
    )

    resp = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=user_block,
        config=gen_cfg,
    )

    trace = f"System:\n{SYSTEM_PROMPT}\n\nUser block:\n{user_block}\n"

    name, args = _extract_function_call(resp)
    model_cls = _TOOL_MODELS.get(name)
    if model_cls is None:
        raise ValueError(f"Unknown tool name from model: {name!r}")

    try:
        payload = model_cls.model_validate(args)
    except ValidationError as e:
        log.warning("Pydantic validation failed for tool %s args=%s: %s", name, args, e)
        raise ValueError(f"Invalid tool arguments for {name}: {e}") from e

    return Action(payload), trace
