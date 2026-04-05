"""Compact LLM context: goals, recent logs, last parsed actions."""
from __future__ import annotations

from collections import deque
from typing import Any

from bot.storage import JsonStorage

# user_id -> deque of last 3 action dicts (JSON-serializable)
_recent_actions: dict[int, deque[dict[str, Any]]] = {}


def record_parsed_action(user_id: int, action: dict[str, Any], max_items: int = 3) -> None:
    if user_id not in _recent_actions:
        _recent_actions[user_id] = deque(maxlen=max_items)
    # shallow copy to avoid accidental mutation
    _recent_actions[user_id].append(dict(action))


def get_recent_actions(user_id: int) -> list[dict[str, Any]]:
    q = _recent_actions.get(user_id)
    if not q:
        return []
    return list(q)


def build_compact_context(user_id: int, storage: JsonStorage | None = None) -> dict[str, Any]:
    storage = storage or JsonStorage.get()
    goals = storage.get_goals()
    # last 3 calendar days of logs (spec: last 3 days)
    recent_logs = storage.get_recent_logs(days=3)
    recent_logs.sort(key=lambda e: (e.get("date", ""), e.get("timestamp", "")))
    return {
        "goals": {
            "daily": goals.get("daily"),
            "weekly": goals.get("weekly"),
            "monthly": goals.get("monthly"),
        },
        "recent_logs": recent_logs,
        "last_parsed_actions": get_recent_actions(user_id),
    }
    