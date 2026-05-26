"""Isolated per-chat session base (asyncio)."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from chat.messages import SessionInboundMsg, SessionOutboundMsg


class BaseChatSession(ABC):
    """One chat: injected queues + async worker task."""

    def __init__(
        self,
        session_id: str,
        inbound_queue: asyncio.Queue[SessionInboundMsg],
        outbound_queue: asyncio.Queue[SessionOutboundMsg],
    ) -> None:
        self.session_id = session_id
        self.inbound_queue = inbound_queue
        self.outbound_queue = outbound_queue
        self._worker_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._worker_task is not None:
            return
        self._worker_task = asyncio.create_task(
            self.poll_incoming_msg(),
            name=f"session-{self.session_id}",
        )

    async def stop(self, timeout: float | None = 5.0) -> None:
        if self._worker_task is None:
            return
        self._worker_task.cancel()
        try:
            await asyncio.wait_for(self._worker_task, timeout=timeout)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        finally:
            self._worker_task = None

    async def poll_incoming_msg(self) -> None:
        try:
            while True:
                message = await self.inbound_queue.get()
                response_message = await self.handle_msg(message)
                await self.send_output(response_message)
        except asyncio.CancelledError:
            return

    async def send_output(self, message: str) -> None:
        outbound = SessionOutboundMsg(
            session_id=self.session_id,
            message=message,
            time=datetime.now(timezone.utc),
        )
        await self.outbound_queue.put(outbound)

    @abstractmethod
    async def handle_msg(self, message: SessionInboundMsg) -> str:
        """Process one inbound message and return outbound text."""
