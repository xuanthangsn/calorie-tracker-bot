"""Isolated per-chat session base (asyncio)."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from enum import Enum, auto

from chat.messages import IncomingMessage

SendReplyCallback = Callable[[str], Awaitable[None]]


class ChatSessionState(Enum):
    PENDING = auto()
    ACTIVE = auto()


class BaseChatSession(ABC):
    """One chat: private inbox, async worker task, replies via dispatcher-provided callback."""

    def __init__(self, session_id: str, send_reply: SendReplyCallback) -> None:
        self.session_id = session_id
        self._enqueue_reply = send_reply
        self.inbox: asyncio.Queue[IncomingMessage] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._worker_task is not None:
            return
        self._worker_task = asyncio.create_task(
            self._worker_loop(),
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

    async def _worker_loop(self) -> None:
        try:
            while True:
                message = await self.inbox.get()
                await self._handle_request(message)
        except asyncio.CancelledError:
            return

    async def _send_reply(self, text: str) -> None:
        await self._enqueue_reply(text)

    @abstractmethod
    async def _handle_request(self, message: IncomingMessage) -> None:
        """Process one inbound message; use :meth:`_send_reply` to respond."""
