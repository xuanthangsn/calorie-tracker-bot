"""Report text generation (Jinja2 + optional pandas)."""
from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from bot.storage import JsonStorage
from utils.helpers import parse_date, today_local

_TPL_ROOT = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TPL_ROOT)),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)


def _logs_in_range(storage: JsonStorage, start: date, end: date) -> list[dict]:
    data = storage.load()
    logs = data.get("logs") or []
    out = []
    for e in logs:
        try:
            d = parse_date(str(e["date"]))
        except (ValueError, KeyError):
            continue
        if start <= d <= end:
            out.append(e)
    return out


def render_daily(storage: JsonStorage, on_date: date | None = None) -> str:
    on_date = on_date or today_local()
    ds = on_date.isoformat()
    goals = storage.get_goals()
    goal = int(goals.get("daily", 2000))
    logs = storage.get_logs_by_date(ds)
    consumed = sum(int(e.get("total_calories", 0)) for e in logs)
    remaining = goal - consumed
    tpl = _env.get_template("reports/daily.j2")
    return tpl.render(date=ds, consumed=consumed, goal=goal, remaining=remaining)


def render_weekly(storage: JsonStorage, end: date | None = None) -> str:
    end = end or today_local()
    start = end - timedelta(days=6)
    logs = _logs_in_range(storage, start, end)
    total = sum(int(e.get("total_calories", 0)) for e in logs)
    goals = storage.get_goals()
    daily_goal = int(goals.get("daily", 2000))
    days = (end - start).days + 1
    avg = round(total / days) if days else 0
    tpl = _env.get_template("reports/weekly.j2")
    return tpl.render(
        start=start.isoformat(),
        end=end.isoformat(),
        total=total,
        avg_per_day=avg,
        daily_goal=daily_goal,
    )


def render_monthly(storage: JsonStorage, year: int | None = None, month: int | None = None) -> str:
    today = today_local()
    year = year or today.year
    month = month or today.month
    last_day = monthrange(year, month)[1]
    start = date(year, month, 1)
    end = date(year, month, last_day)
    logs = _logs_in_range(storage, start, end)
    total = sum(int(e.get("total_calories", 0)) for e in logs)
    goals = storage.get_goals()
    goal = int(goals.get("monthly", 60000))
    if total > goal:
        comparison = f"Over goal by {total - goal} kcal"
    elif total < goal:
        comparison = f"Under goal by {goal - total} kcal"
    else:
        comparison = "At goal"
    tpl = _env.get_template("reports/monthly.j2")
    return tpl.render(month=f"{year}-{month:02d}", total=total, goal=goal, comparison=comparison)


def render_report_by_kind(kind: str, storage: JsonStorage | None = None) -> str:
    storage = storage or JsonStorage.get()
    k = (kind or "daily").lower()
    if k == "weekly":
        return render_weekly(storage)
    if k == "monthly":
        return render_monthly(storage)
    return render_daily(storage)
