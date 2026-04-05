"""Date/time helpers for logs and reports."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import config


def get_tz() -> ZoneInfo:
    try:
        return ZoneInfo(config.TZ_NAME)
    except Exception:
        return ZoneInfo("UTC")


def today_local() -> date:
    return datetime.now(get_tz()).date()


def now_local_iso() -> str:
    return datetime.now(get_tz()).replace(microsecond=0).isoformat()


def parse_date(s: str) -> date:
    return date.fromisoformat(s)


def date_range_last_n_days(n: int, end: date | None = None) -> list[date]:
    end = end or today_local()
    return [end - timedelta(days=i) for i in range(n)][::-1]
