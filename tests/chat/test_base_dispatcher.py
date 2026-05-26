"""Tests for generic chat.dispatcher.BaseDispatcher."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from chat.dispatcher import BaseDispatcher, BaseMessagePayload
from chat.messages import SessionInboundMsg, SessionOutboundMsg
from chat.session import BaseChatSession


@dataclass(frozen=True)
class FakePayload(BaseMessagePayload):
    session_id: str
    text: str
    time: datetime


class FakeSession(BaseChatSession):
    def __init__(self, session_id: str, inbound_queue, outbound_queue) -> None:
        super().__init__(session_id, inbound_queue, outbound_queue)
        self.handled: list[SessionInboundMsg] = []

    async def handle_msg(self, message: SessionInboundMsg) -> str:
        self.handled.append(message)
        return f"ack:{message.message}"


class FakeDispatcher(BaseDispatcher[FakePayload]):
    name = "fake"

    def parse_raw_data(self, raw_data: dict) -> FakePayload:
        return FakePayload(
            session_id=str(raw_data["session_id"]),
            text=str(raw_data["text"]),
            time=raw_data.get("time", datetime.now(timezone.utc)),
        )

    def create_session_id(self, payload: FakePayload) -> str:
        return payload.session_id

    def get_input_msg_from_parsed_data(self, payload: FakePayload) -> SessionInboundMsg:
        return SessionInboundMsg(message=payload.text, time=payload.time)

    async def _poll_inbound(self) -> None:
        await asyncio.sleep(3600)

    async def _send_outgoing(self, message: SessionOutboundMsg) -> None:
        return


def test_process_incoming_msg_registers_session_and_enqueues() -> None:
    async def run() -> None:
        dispatcher = FakeDispatcher(
            session_factory=lambda sid, in_q, out_q: FakeSession(sid, in_q, out_q),
            inbound_queue_maxsize=8,
            outbound_queue_maxsize=16,
        )
        await dispatcher.process_incoming_msg({"session_id": "a", "text": "hello"})
        await asyncio.sleep(0.05)

        async with dispatcher._session_lock:
            record = dispatcher._registered_sessions["a"]
            session = record.session

        assert isinstance(session, FakeSession)
        assert session.outbound_queue is dispatcher._outbound_queue
        assert len(session.handled) == 1
        assert session.handled[0].message == "hello"

        outbound = await asyncio.wait_for(dispatcher._outbound_queue.get(), timeout=0.3)
        assert outbound.session_id == "a"
        assert outbound.message == "ack:hello"

        await dispatcher.shutdown()

    asyncio.run(run())

