"""Tests for chat.telegram_dispatcher.TelegramDispatcher."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message

from chat.messages import SessionInboundMsg, SessionOutboundMsg
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
    def __init__(self, session_id: str, inbound_queue, outbound_queue) -> None:
        super().__init__(session_id, inbound_queue, outbound_queue)
        self.handled: list[SessionInboundMsg] = []

    async def handle_msg(self, message: SessionInboundMsg) -> str:
        self.handled.append(message)
        return "ok"


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
            lambda sid, in_q, out_q: StubChatSession(sid, in_q, out_q),
        )
        assert dispatcher.get_name() == "telegram"
        assert TelegramDispatcher.get_name() == "telegram"

    def test_empty_bot_token_raises(self) -> None:
        with pytest.raises(ValueError, match="bot_token"):
            TelegramDispatcher("", lambda sid, in_q, out_q: StubChatSession(sid, in_q, out_q))

    def test_whitespace_bot_token_raises(self) -> None:
        with pytest.raises(ValueError, match="bot_token"):
            TelegramDispatcher("   ", lambda sid, in_q, out_q: StubChatSession(sid, in_q, out_q))


class TestTelegramDispatcherPayloadMapping:
    def test_create_session_id(self) -> None:
        dispatcher = TelegramDispatcher(
            _VALID_TEST_BOT_TOKEN,
            lambda sid, in_q, out_q: StubChatSession(sid, in_q, out_q),
        )
        payload = dispatcher.parse_raw_data({"chat_id": 42, "text": "hi", "message_id": 1})
        assert dispatcher.create_session_id(payload) == "42"

    def test_to_session_inbound_message(self) -> None:
        dispatcher = TelegramDispatcher(
            _VALID_TEST_BOT_TOKEN,
            lambda sid, in_q, out_q: StubChatSession(sid, in_q, out_q),
        )
        payload = dispatcher.parse_raw_data(
            {
                "chat_id": 100,
                "text": "hello",
                "message_id": 1,
                "time": datetime.now(timezone.utc),
            }
        )
        incoming = dispatcher.get_input_msg_from_parsed_data(payload)
        assert incoming.message == "hello"


class TestTelegramDispatcherRouting:
    def test_process_incoming_msg_creates_session_and_processes(self) -> None:
        async def run() -> None:
            dispatcher = TelegramDispatcher(
                _VALID_TEST_BOT_TOKEN,
                lambda sid, in_q, out_q: StubChatSession(sid, in_q, out_q),
            )
            await dispatcher.process_incoming_msg(
                {"chat_id": 100, "text": "hello", "message_id": 1}
            )
            for _ in range(50):
                async with dispatcher._session_lock:
                    record = dispatcher._registered_sessions.get("100")
                    session = record.session if record is not None else None
                if session is not None and session.handled:
                    break
                await asyncio.sleep(0.02)
            async with dispatcher._session_lock:
                session = dispatcher._registered_sessions["100"].session
            assert len(session.handled) == 1
            assert session.handled[0].message == "hello"
            outbound = await dispatcher._outbound_queue.get()
            assert outbound.session_id == "100"
            assert outbound.message == "ok"
            await dispatcher.shutdown()

        asyncio.run(run())


class TestTelegramDispatcherOutbound:
    def test_send_outgoing_calls_send_message(self) -> None:
        async def run() -> None:
            dispatcher = TelegramDispatcher(
                _VALID_TEST_BOT_TOKEN,
                lambda sid, in_q, out_q: StubChatSession(sid, in_q, out_q),
            )
            dispatcher._bot.send_message = AsyncMock()
            await dispatcher._send_outgoing(
                SessionOutboundMsg(
                    session_id="123",
                    message="reply text",
                    time=datetime.now(timezone.utc),
                )
            )
            dispatcher._bot.send_message.assert_awaited_once_with(
                chat_id=123,
                text="reply text",
            )

        asyncio.run(run())

    def test_send_outgoing_invalid_session_id_is_dropped(self) -> None:
        async def run() -> None:
            dispatcher = TelegramDispatcher(
                _VALID_TEST_BOT_TOKEN,
                lambda sid, in_q, out_q: StubChatSession(sid, in_q, out_q),
            )
            dispatcher._bot.send_message = AsyncMock()
            await dispatcher._send_outgoing(
                SessionOutboundMsg(
                    session_id="bad-id",
                    message="text",
                    time=datetime.now(timezone.utc),
                )
            )
            dispatcher._bot.send_message.assert_not_called()

        asyncio.run(run())
