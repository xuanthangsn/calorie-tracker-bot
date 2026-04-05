"""Bot startup: polling + scheduler."""
from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import config
from bot.handlers import router
from scheduler import setup_scheduler


async def main() -> None:
    if not config.TELEGRAM_TOKEN:
        logging.error("TELEGRAM_TOKEN is required")
        sys.exit(1)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    bot = Bot(
        config.TELEGRAM_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    # setup scheduler
    sched = setup_scheduler(bot)
    sched.start()

    try:
        await dp.start_polling(bot)
    finally:
        sched.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
