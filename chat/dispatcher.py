"""Central gateway: registry, global outbox, inbound/outbound asyncio tasks."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import ClassVar

from chat.messages import IncomingMessage, OutgoingMessage
from chat.session import BaseChatSession, SendReplyCallback


class BaseDispatcher(ABC):
    """Async global outbox, session map, and abstract I/O hooks (single event loop)."""

    name: ClassVar[str]

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if cls is BaseDispatcher:
            return
        if "name" not in cls.__dict__:
            raise TypeError(f"{cls.__name__} must define class attribute 'name'")
        if not isinstance(cls.name, str) or not cls.name:
            raise TypeError(f"{cls.__name__}.name must be a non-empty str")

    @classmethod
    def get_name(cls) -> str:
        return cls.name

    def __init__(
        self,
        session_factory: Callable[[str, SendReplyCallback], BaseChatSession],
    ) -> None:
        self._session_factory = session_factory
        self._global_outbox: asyncio.Queue[OutgoingMessage] = asyncio.Queue()
        self._active_sessions: dict[str, BaseChatSession] = {}
        self._session_lock = asyncio.Lock()

    async def run(self) -> None:
        """Run until inbound polling stops or the process is cancelled."""
        outbound_task = asyncio.create_task(self._process_outbound(), name="outbound")
        inbound_task = asyncio.create_task(self._poll_inbound(), name="inbound")
        try:
            await inbound_task
        finally:
            for task in (outbound_task, inbound_task):
                task.cancel()
            await asyncio.gather(outbound_task, inbound_task, return_exceptions=True)

    def _make_send_reply_callback(self, session_id: str) -> SendReplyCallback:
        async def send_reply(text: str) -> None:
            await self._global_outbox.put(OutgoingMessage(session_id, text))

        return send_reply

    def _create_session(self, session_id: str) -> BaseChatSession:
        return self._session_factory(session_id, self._make_send_reply_callback(session_id))

    async def _process_inbound_msg(self, msg_payload: dict) -> None:
        session_id = self._generate_session_id(msg_payload)
        await self._route_msg(session_id, msg_payload)

    async def _route_msg(self, session_id: str, msg_payload: dict) -> None:
        incoming = self._to_incoming_message(session_id, msg_payload)
        async with self._session_lock:
            if session_id not in self._active_sessions:
                session = self._create_session(session_id)
                await session.start()
                self._active_sessions[session_id] = session
            session = self._active_sessions[session_id]
        await session.inbox.put(incoming)

    @abstractmethod
    def _generate_session_id(self, msg_payload: dict) -> str:
        """Derive a stable session id from a channel-specific inbound payload."""

    @abstractmethod
    def _to_incoming_message(
        self, session_id: str, msg_payload: dict
    ) -> IncomingMessage:
        """Build the session inbox envelope from a channel-specific payload."""

    @abstractmethod
    async def _poll_inbound(self) -> None:
        """Poll network until cancelled; channel I/O calls :meth:`_process_inbound_msg` per message."""

    @abstractmethod
    async def _send_outgoing(self, message: OutgoingMessage) -> None:
        """Send an outgoing message to the network."""

    async def _process_outbound(self) -> None:
        """Consume :attr:`_global_outbox` and send to network."""
        try:
            while True:
                message = await self._global_outbox.get()
                await self._send_outgoing(message)
        except asyncio.CancelledError:
            return
