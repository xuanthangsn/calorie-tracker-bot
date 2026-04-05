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
from bot.parser import Action, MealItem, parse_user_message
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


def _action_to_dict(a: Action) -> dict[str, Any]:
    return {
        "action": a.action,
        "data": a.data,
        "target_meal_id": a.target_meal_id,
        "clarification_question": a.clarification_question,
    }


async def _execute_action(message: Message, action: Action, storage: JsonStorage) -> str:
    if action.action == "refuse":
        return _render_response("refuse")

    if action.action == "ask_clarification":
        q = action.clarification_question or "Which meal or date?"
        return _render_response("clarification", question=q)

    if action.action == "get_report":
        data = action.data or {}
        kind = (
            data.get("report")
            or data.get("period")
            or data.get("kind")
            or "daily"
        )
        text = render_report_by_kind(str(kind), storage)
        return _render_response("report", report_text=text)

    if action.action == "set_goal":
        data = action.data or {}
        updates = {}
        for k in ("daily", "weekly", "monthly"):
            if k in data and data[k] is not None:
                try:
                    updates[k] = int(data[k])
                except (TypeError, ValueError):
                    pass
        if not updates:
            return _render_response(
                "clarification",
                question="Set daily, weekly, or monthly goal (kcal)?",
            )
        storage.update_goals(updates)
        g = storage.get_goals()
        return _render_response(
            "report",
            report_text=f"Goals: daily {g.get('daily')}, weekly {g.get('weekly')}, monthly {g.get('monthly')}.",
        )

    if action.action == "delete_meal":
        lid = action.target_meal_id
        if lid is None:
            return _render_response(
                "clarification",
                question="Which log ID should I delete?",
            )
        ok = storage.delete_log(int(lid))
        if not ok:
            return _render_response(
                "report",
                report_text=f"No log #{lid}.",
            )
        return _render_response("report", report_text=f"Deleted log #{lid}.")

    if action.action == "edit_meal":
        lid = action.target_meal_id
        if lid is None:
            return _render_response(
                "clarification",
                question="Which log ID should I edit?",
            )
        data = action.data or {}
        patch: dict[str, Any] = {}
        if "meal_type" in data:
            patch["meal_type"] = data["meal_type"]
        if "date" in data:
            patch["date"] = str(data["date"])
        if "items" in data and data["items"]:
            raw_items = [
                MealItem(
                    food=str(i.get("food", "")),
                    quantity=str(i.get("quantity", "100 g")),
                    calories=i.get("calories"),
                )
                for i in data["items"]
                if i.get("food")
            ]
            resolved = resolve_meal_items(raw_items, storage)
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

    if action.action == "log_meal":
        data = action.data or {}
        meal_type = str(data.get("meal_type", "meal"))
        d = str(data.get("date") or today_local().isoformat())
        raw_items = data.get("items") or []
        if not raw_items:
            return _render_response(
                "clarification",
                question="What foods and amounts?",
            )
        items = [
            MealItem(
                food=str(i.get("food", "")),
                quantity=str(i.get("quantity", "100 g")),
                calories=i.get("calories"),
            )
            for i in raw_items
            if i.get("food")
        ]
        if not items:
            return _render_response(
                "clarification",
                question="What foods and amounts?",
            )
        resolved = resolve_meal_items(items, storage)
        total = sum(m.calories or 0 for m in resolved)
        entry = {
            "date": d,
            "meal_type": meal_type,
            "items": [m.model_dump() for m in resolved],
            "total_calories": total,
            "timestamp": now_local_iso(),
        }
        saved = storage.add_log(entry)
        return _render_response(
            "logged",
            meal_type=meal_type,
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

    # if st == TrackerStates.awaiting_clarification.state:
    #     data = await state.get_data()
    #     pending = data.get("pending_action")
    #     if pending:
    #         user_text = (
    #             f"Pending action (JSON): {json.dumps(pending, ensure_ascii=False)}\n"
    #             f"User follow-up: {user_text}"
    #         )
    #     await state.set_state(TrackerStates.default)
    #     await state.update_data(pending_action=None)

    ctx = build_compact_context(uid, storage)
    try:
        resp, llm_request_str = parse_user_message(user_text, ctx)
    except Exception as e:
        log.exception("parse failed: %s", e)
        # await message.answer(_render_response("clarification", question="Repeat that?"))
        await message.answer("There was an error parsing your message. Please try again.")
        return

    resp = str(resp)
    
    print(f"LLM Request: \n{llm_request_str}")
    print(f"LLM Response: \n{resp}")
    # record_parsed_action(uid, _action_to_dict(action))

    # if action.action == "ask_clarification":
    #     await state.set_state(TrackerStates.awaiting_clarification)
    #     await state.update_data(pending_action=_action_to_dict(action))

    # reply = await _execute_action(message, action, storage)
    await message.answer(resp)
