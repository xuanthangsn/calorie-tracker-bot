"""Message handlers: parse → act → templated reply."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from jinja2 import Environment, FileSystemLoader

import config
from bot.food_lookup import resolve_meal_items
from bot.fsm_states import TrackerStates
from bot.action import (
    Action,
    AskClarificationAction,
    DeleteMealAction,
    EditMealAction,
    GetReportAction,
    LogMealAction,
    RefuseAction,
    SetGoalAction,
)
from bot.parser import parse_user_message
from bot.reports import render_report_by_kind
from bot.storage import JsonStorage
from utils.context_builder import build_compact_context, record_parsed_action
from utils.helpers import now_local_iso, today_local

log = logging.getLogger(__name__)

router = Router()

_TPL_ROOT = Path(__file__).parent / "templates"
_response_env = Environment(
    loader=FileSystemLoader(str(_TPL_ROOT)),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)


def _render_response(name: str, **ctx: Any) -> str:
    tpl = _response_env.get_template(f"responses/{name}.j2")
    return tpl.render(**ctx).strip()


def _action_to_dict(wrapped: Action) -> dict[str, Any]:
    return wrapped.model_dump(mode="json")


async def _execute_action(message: Message, wrapped: Action, storage: JsonStorage) -> str:
    a = wrapped.root

    if isinstance(a, RefuseAction):
        return _render_response("refuse")

    if isinstance(a, AskClarificationAction):
        return _render_response("clarification", question=a.clarification_question)

    if isinstance(a, GetReportAction):
        text = render_report_by_kind(a.period, storage)
        return _render_response("report", report_text=text)

    if isinstance(a, SetGoalAction):
        updates: dict[str, int] = {}
        if a.daily is not None:
            updates["daily"] = a.daily
        if a.weekly is not None:
            updates["weekly"] = a.weekly
        if a.monthly is not None:
            updates["monthly"] = a.monthly
        if not updates:
            return _render_response(
                "clarification",
                question="Set daily, weekly, or monthly goal (kcal)?",
            )
        storage.update_goals(updates)
        g = storage.get_goals()
        return _render_response(
            "report",
            report_text=(
                f"Goals: daily {g.get('daily')}, weekly {g.get('weekly')}, "
                f"monthly {g.get('monthly')}."
            ),
        )

    if isinstance(a, DeleteMealAction):
        lid = a.target_meal_id
        ok = storage.delete_log(int(lid))
        if not ok:
            return _render_response("report", report_text=f"No log #{lid}.")
        return _render_response("report", report_text=f"Deleted log #{lid}.")

    if isinstance(a, EditMealAction):
        lid = a.target_meal_id
        patch: dict[str, Any] = {}
        if a.meal_type is not None:
            patch["meal_type"] = a.meal_type
        if a.date is not None:
            patch["date"] = a.date
        if a.items:
            resolved = resolve_meal_items(list(a.items), storage)
            patch["items"] = [m.model_dump() for m in resolved]
            patch["total_calories"] = sum(m.calories or 0 for m in resolved)
        if not patch:
            return _render_response(
                "clarification",
                question="What should change for this log?",
            )
        updated = storage.update_log(int(lid), patch)
        if not updated:
            return _render_response("report", report_text=f"No log #{lid}.")
        return _render_response(
            "edited",
            log_id=lid,
            total=int(updated.get("total_calories", 0)),
        )

    if isinstance(a, LogMealAction):
        d = a.date or today_local().isoformat()
        if not a.items:
            return _render_response(
                "clarification",
                question="What foods and amounts?",
            )
        resolved = resolve_meal_items(list(a.items), storage)
        total = sum(m.calories or 0 for m in resolved)
        entry = {
            "date": d,
            "meal_type": a.meal_type,
            "items": [m.model_dump() for m in resolved],
            "total_calories": total,
            "timestamp": now_local_iso(),
        }
        saved = storage.add_log(entry)
        return _render_response(
            "logged",
            meal_type=a.meal_type,
            date=d,
            total=total,
            log_id=saved["id"],
        )

    return _render_response("refuse")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.set_state(TrackerStates.default)
    await message.answer(
        "Calorie log. Send meals, goals, or ask for daily/weekly/monthly report."
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Log: e.g. breakfast 2 eggs and toast. Edit: change log #3. "
        "Report: weekly summary. Goals: set daily goal 1800."
    )


@router.message(F.text)
async def on_text(message: Message, state: FSMContext) -> None:
    if not message.text or not message.from_user:
        return
    uid = message.from_user.id
    storage = JsonStorage.get()
    st = await state.get_state()
    user_text = message.text.strip()

    if st == TrackerStates.awaiting_clarification.state:
        data = await state.get_data()
        pending = data.get("pending_action")
        if pending:
            user_text = (
                f"Pending action (JSON): {json.dumps(pending, ensure_ascii=False)}\n"
                f"User follow-up: {user_text}"
            )
        await state.set_state(TrackerStates.default)
        await state.update_data(pending_action=None)

    ctx = build_compact_context(uid, storage)
    try:
        parsed, llm_request_str = parse_user_message(user_text, ctx)
    except Exception as e:
        log.exception("parse failed: %s", e)
        await message.answer("There was an error parsing your message. Please try again.")
        return

    log.debug("LLM request trace: %s", llm_request_str)
    record_parsed_action(uid, _action_to_dict(parsed))

    if isinstance(parsed.root, AskClarificationAction):
        await state.set_state(TrackerStates.awaiting_clarification)
        await state.update_data(pending_action=_action_to_dict(parsed))

    reply = await _execute_action(message, parsed, storage)
    await message.answer(reply)
