"""APScheduler: weekly (Sun 8 PM) and monthly (1st 8 PM) auto-reports."""
from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import config
from bot.reports import render_monthly, render_weekly
from bot.storage import JsonStorage

log = logging.getLogger(__name__)


def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(config.TZ_NAME)
    except Exception:
        return ZoneInfo("UTC")


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    sched = AsyncIOScheduler(timezone=_tz())

    async def push_weekly() -> None:
        if config.TELEGRAM_CHAT_ID is None:
            log.warning("TELEGRAM_CHAT_ID not set; skip weekly report")
            return
        text = render_weekly(JsonStorage.get())
        await bot.send_message(config.TELEGRAM_CHAT_ID, text)

    async def push_monthly() -> None:
        if config.TELEGRAM_CHAT_ID is None:
            log.warning("TELEGRAM_CHAT_ID not set; skip monthly report")
            return
        text = render_monthly(JsonStorage.get())
        await bot.send_message(config.TELEGRAM_CHAT_ID, text)

    sched.add_job(
        push_weekly,
        CronTrigger(day_of_week="sun", hour=20, minute=0, timezone=_tz()),
        id="weekly_report",
        replace_existing=True,
    )
    sched.add_job(
        push_monthly,
        CronTrigger(day=1, hour=20, minute=0, timezone=_tz()),
        id="monthly_report",
        replace_existing=True,
    )
    return sched
