"""Bot startup: TelegramDispatcher + async chat sessions on one event loop."""
from __future__ import annotations

import asyncio
import logging
import sys

import config
from chat.echo_session import EchoChatSession
from chat.telegram_dispatcher import TelegramDispatcher


async def main() -> None:
    if not config.TELEGRAM_TOKEN:
        logging.error("TELEGRAM_TOKEN is required")
        sys.exit(1)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    dispatcher = TelegramDispatcher(
        bot_token=config.TELEGRAM_TOKEN,
        session_factory=lambda session_id, inbound_queue, outbound_queue: EchoChatSession(
            session_id, inbound_queue, outbound_queue
        ),
    )
    logging.info("Telegram dispatcher starting")
    await dispatcher.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("shutting down")
