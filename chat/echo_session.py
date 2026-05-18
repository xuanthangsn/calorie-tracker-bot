"""Minimal session that echoes inbound text (development / wiring stub)."""

from __future__ import annotations

from chat.messages import IncomingMessage
from chat.session import BaseChatSession


class EchoChatSession(BaseChatSession):
    """Echo user text back through the dispatcher outbox."""

    async def _handle_request(self, message: IncomingMessage) -> None:
        await self._send_reply(f"You said: {message.text}")
