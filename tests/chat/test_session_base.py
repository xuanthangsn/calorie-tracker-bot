"""Tests for chat.session.BaseChatSession."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from chat.messages import SessionInboundMsg
from chat.session import BaseChatSession


class PrefixSession(BaseChatSession):
    async def handle_msg(self, message: SessionInboundMsg) -> str:
        return f"reply:{message.message}"


def test_session_polls_inbound_and_emits_outbound() -> None:
    async def run() -> None:
        inbound: asyncio.Queue[SessionInboundMsg] = asyncio.Queue()
        outbound = asyncio.Queue()
        session = PrefixSession("s1", inbound, outbound)
        await session.start()
        await inbound.put(
            SessionInboundMsg(
                message="hello",
                time=datetime.now(timezone.utc),
            )
        )

        outgoing = await asyncio.wait_for(outbound.get(), timeout=0.3)
        assert outgoing.session_id == "s1"
        assert outgoing.message == "reply:hello"
        assert outgoing.time.tzinfo is not None
        await session.stop()

    asyncio.run(run())

