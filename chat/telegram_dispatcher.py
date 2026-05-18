"""Telegram network I/O via aiogram on a single asyncio event loop."""

from __future__ import annotations

import logging
from collections.abc import Callable

from aiogram import Bot, Dispatcher as AiogramDispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message

from chat.dispatcher import BaseDispatcher
from chat.messages import IncomingMessage, OutgoingMessage
from chat.session import BaseChatSession, SendReplyCallback

logger = logging.getLogger(__name__)


def _text_from_message(message: Message) -> str | None:
    if message.text is None:
        return None
    stripped = message.text.strip()
    return stripped or None


class TelegramDispatcher(BaseDispatcher):
    """Poll Telegram and route messages to async chat sessions on one event loop."""

    name = "telegram"

    def __init__(
        self,
        bot_token: str,
        session_factory: Callable[[str, SendReplyCallback], BaseChatSession],
        *,
        parse_mode: ParseMode = ParseMode.HTML,
    ) -> None:
        if not bot_token or not bot_token.strip():
            raise ValueError("bot_token must be a non-empty string")
        super().__init__(session_factory)
        self._bot = Bot(
            bot_token.strip(),
            default=DefaultBotProperties(parse_mode=parse_mode),
        )
        self._router = Router()
        self._aiogram_dp = AiogramDispatcher()
        self._aiogram_dp.include_router(self._router)
        self._register_handlers()

    def _generate_session_id(self, msg_payload: dict) -> str:
        # return f"{self.name}:{msg_payload['chat_id']}"
        return str(msg_payload['chat_id'])
   

    def _to_incoming_message(
        self, session_id: str, msg_payload: dict
    ) -> IncomingMessage:
        return IncomingMessage(session_id, msg_payload["text"])

    def _register_handlers(self) -> None:
        @self._router.message(F.text)
        async def on_text(message: Message) -> None:
            try:
                text = _text_from_message(message)
                if text is None or message.chat is None:
                    return
                await self._process_inbound_msg(
                    {
                        "chat_id": message.chat.id,
                        "text": text,
                        "message_id": message.message_id,
                    }
                )
            except Exception:
                logger.exception("failed to process inbound Telegram message")

    async def _poll_inbound(self) -> None:
        await self._aiogram_dp.start_polling(self._bot, handle_signals=False)

    async def _send_outgoing(self, message: OutgoingMessage) -> None:
        try:
            chat_id = int(message.session_id)
        except ValueError:
            logger.error("invalid outbound session_id: %r", message.session_id)
            return
        try:
            await self._bot.send_message(chat_id=chat_id, text=message.text)
        except Exception:
            logger.exception(
                "failed to send Telegram message chat_id=%s session_id=%s",
                chat_id,
                message.session_id,
            )
