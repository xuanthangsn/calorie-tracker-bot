"""Tests for chat.telegram_dispatcher.TelegramDispatcher."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message

from chat.messages import IncomingMessage, OutgoingMessage
from chat.session import BaseChatSession
from chat.telegram_dispatcher import (
    TelegramDispatcher,
    _session_id_from_message,
    _text_from_message,
)

_VALID_TEST_BOT_TOKEN = "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi"


def _message(text: str | None, chat_id: int = 100, user_id: int = 200) -> Message:
    message = MagicMock(spec=Message)
    message.text = text
    message.message_id = 1
    message.chat = MagicMock()
    message.chat.id = chat_id
    message.from_user = MagicMock()
    message.from_user.id = user_id
    return message


class StubChatSession(BaseChatSession):
    def __init__(self, session_id: str, send_reply) -> None:
        super().__init__(session_id, send_reply)
        self.handled: list[IncomingMessage] = []

    async def _handle_request(self, message: IncomingMessage) -> None:
        self.handled.append(message)
        await self._send_reply("ok")


class TestMessageParsingHelpers:
    def test_session_id_from_message(self) -> None:
        assert _session_id_from_message(_message("hi", chat_id=42)) == "42"

    def test_text_from_message_strips(self) -> None:
        assert _text_from_message(_message("  hello  ")) == "hello"

    def test_text_from_message_returns_none_for_blank(self) -> None:
        assert _text_from_message(_message("   ")) is None
        assert _text_from_message(_message(None)) is None


class TestTelegramDispatcherInit:
    def test_name_and_get_name(self) -> None:
        assert TelegramDispatcher.name == "telegram"
        dispatcher = TelegramDispatcher(
            _VALID_TEST_BOT_TOKEN,
            lambda sid, send_reply: StubChatSession(sid, send_reply),
        )
        assert dispatcher.get_name() == "telegram"
        assert TelegramDispatcher.get_name() == "telegram"

    def test_empty_bot_token_raises(self) -> None:
        with pytest.raises(ValueError, match="bot_token"):
            TelegramDispatcher("", lambda sid, send_reply: StubChatSession(sid, send_reply))

    def test_whitespace_bot_token_raises(self) -> None:
        with pytest.raises(ValueError, match="bot_token"):
            TelegramDispatcher("   ", lambda sid, send_reply: StubChatSession(sid, send_reply))


class TestTelegramDispatcherPayloadMapping:
    def test_generate_session_id(self) -> None:
        dispatcher = TelegramDispatcher(
            _VALID_TEST_BOT_TOKEN,
            lambda sid, send_reply: StubChatSession(sid, send_reply),
        )
        assert dispatcher._generate_session_id({"chat_id": 42, "text": "hi"}) == "42"

    def test_to_incoming_message(self) -> None:
        dispatcher = TelegramDispatcher(
            _VALID_TEST_BOT_TOKEN,
            lambda sid, send_reply: StubChatSession(sid, send_reply),
        )
        incoming = dispatcher._to_incoming_message(
            "100", {"chat_id": 100, "text": "hello", "message_id": 1}
        )
        assert incoming.session_id == "100"
        assert incoming.text == "hello"


class TestTelegramDispatcherRouting:
    def test_process_inbound_msg_creates_session_and_processes(self) -> None:
        async def run() -> None:
            dispatcher = TelegramDispatcher(
                _VALID_TEST_BOT_TOKEN,
                lambda sid, send_reply: StubChatSession(sid, send_reply),
            )
            await dispatcher._process_inbound_msg(
                {"chat_id": 100, "text": "hello", "message_id": 1}
            )
            for _ in range(50):
                async with dispatcher._session_lock:
                    session = dispatcher._active_sessions.get("100")
                if session is not None and session.handled:
                    break
                await asyncio.sleep(0.02)
            async with dispatcher._session_lock:
                session = dispatcher._active_sessions["100"]
            assert len(session.handled) == 1
            assert session.handled[0].text == "hello"

        asyncio.run(run())


class TestTelegramDispatcherOutbound:
    def test_send_outgoing_calls_send_message(self) -> None:
        async def run() -> None:
            dispatcher = TelegramDispatcher(
                _VALID_TEST_BOT_TOKEN,
                lambda sid, send_reply: StubChatSession(sid, send_reply),
            )
            dispatcher._bot.send_message = AsyncMock()
            await dispatcher._send_outgoing(OutgoingMessage("123", "reply text"))
            dispatcher._bot.send_message.assert_awaited_once_with(
                chat_id=123,
                text="reply text",
            )

        asyncio.run(run())

    def test_send_outgoing_invalid_session_id_is_dropped(self) -> None:
        async def run() -> None:
            dispatcher = TelegramDispatcher(
                _VALID_TEST_BOT_TOKEN,
                lambda sid, send_reply: StubChatSession(sid, send_reply),
            )
            dispatcher._bot.send_message = AsyncMock()
            await dispatcher._send_outgoing(OutgoingMessage("bad-id", "text"))
            dispatcher._bot.send_message.assert_not_called()

        asyncio.run(run())
