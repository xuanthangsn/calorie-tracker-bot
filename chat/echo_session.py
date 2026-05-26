"""Minimal session that echoes inbound text (development / wiring stub)."""

from __future__ import annotations

from chat.messages import SessionInboundMsg
from chat.session import BaseChatSession


class EchoChatSession(BaseChatSession):
    """Echo user text back through the dispatcher outbound queue."""

    async def handle_msg(self, message: SessionInboundMsg) -> str:
        return f"You said: {message.message}"
