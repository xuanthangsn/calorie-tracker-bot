"""Telegram network I/O via aiogram on a single asyncio event loop."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from aiogram import Bot, Dispatcher as AiogramDispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message

from chat.dispatcher import BaseDispatcher, BaseMessagePayload
from chat.messages import SessionInboundMsg, SessionOutboundMsg
from chat.session import BaseChatSession

logger = logging.getLogger(__name__)


def _text_from_message(message: Message) -> str | None:
    if message.text is None:
        return None
    stripped = message.text.strip()
    return stripped or None


def _session_id_from_message(message: Message) -> str:
    if message.chat is None:
        raise ValueError("message.chat is required")
    return str(message.chat.id)


@dataclass(frozen=True)
class TelegramMessagePayload(BaseMessagePayload):
    chat_id: int
    text: str
    message_id: int
    time: datetime


class TelegramDispatcher(BaseDispatcher[TelegramMessagePayload]):
    """Poll Telegram and route messages to async chat sessions on one event loop."""

    name = "telegram"

    def __init__(
        self,
        bot_token: str,
        session_factory: Callable[
            [str, asyncio.Queue[SessionInboundMsg], asyncio.Queue[SessionOutboundMsg]],
            BaseChatSession,
        ],
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

    def parse_raw_data(self, raw_data: Any) -> TelegramMessagePayload:
        if isinstance(raw_data, Message):
            text = _text_from_message(raw_data)
            if text is None:
                raise ValueError("telegram message has no text payload")
            if raw_data.chat is None:
                raise ValueError("telegram message has no chat")
            return TelegramMessagePayload(
                chat_id=raw_data.chat.id,
                text=text,
                message_id=raw_data.message_id,
                time=datetime.now(timezone.utc),
            )
        if isinstance(raw_data, dict):
            return TelegramMessagePayload(
                chat_id=int(raw_data["chat_id"]),
                text=str(raw_data["text"]),
                message_id=int(raw_data.get("message_id", 0)),
                time=raw_data.get("time", datetime.now(timezone.utc)),
            )
        raise TypeError("raw_data must be aiogram Message or dict")

    def create_session_id(self, payload: TelegramMessagePayload) -> str:
        return str(payload.chat_id)

    def get_input_msg_from_parsed_data(
        self, payload: TelegramMessagePayload
    ) -> SessionInboundMsg:
        return SessionInboundMsg(message=payload.text, time=payload.time)

    def _register_handlers(self) -> None:
        @self._router.message(F.text)
        async def on_text(message: Message) -> None:
            try:
                text = _text_from_message(message)
                if text is None or message.chat is None:
                    return
                await self.process_incoming_msg(message)
            except Exception:
                logger.exception("failed to process inbound Telegram message")

    async def _poll_inbound(self) -> None:
        await self._aiogram_dp.start_polling(self._bot, handle_signals=False)

    async def _send_outgoing(self, message: SessionOutboundMsg) -> None:
        try:
            chat_id = int(message.session_id)
        except ValueError:
            logger.error("invalid outbound session_id: %r", message.session_id)
            return
        try:
            await self._bot.send_message(chat_id=chat_id, text=message.message)
        except Exception:
            logger.exception(
                "failed to send Telegram message chat_id=%s session_id=%s",
                chat_id,
                message.session_id,
            )
