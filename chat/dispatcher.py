"""Central gateway: registry, session wiring, inbound/outbound asyncio tasks."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ClassVar, Generic, TypeVar

from chat.messages import SessionInboundMsg, SessionOutboundMsg
from chat.session import BaseChatSession


class BaseMessagePayload(ABC):
    """Typed parsed payload from a concrete transport."""


T_MsgPayload = TypeVar("T_MsgPayload", bound=BaseMessagePayload)


@dataclass
class SessionRecord(Generic[T_MsgPayload]):
    """Everything dispatcher tracks per session."""

    session: BaseChatSession
    inbound_queue: asyncio.Queue[SessionInboundMsg]
    msg_payload: T_MsgPayload


class BaseDispatcher(ABC, Generic[T_MsgPayload]):
    """Async generic dispatcher with transport-specific payload parsing."""

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
        session_factory: Callable[
            [str, asyncio.Queue[SessionInboundMsg], asyncio.Queue[SessionOutboundMsg]],
            BaseChatSession,
        ],
        *,
        inbound_queue_maxsize: int = 64,
        outbound_queue_maxsize: int = 256,
    ) -> None:
        if inbound_queue_maxsize <= 0:
            raise ValueError("inbound_queue_maxsize must be greater than 0")
        if outbound_queue_maxsize <= 0:
            raise ValueError("outbound_queue_maxsize must be greater than 0")
        self._session_factory = session_factory
        self._inbound_queue_maxsize = inbound_queue_maxsize
        self._outbound_queue: asyncio.Queue[SessionOutboundMsg] = asyncio.Queue(
            maxsize=outbound_queue_maxsize
        )
        self._registered_sessions: dict[str, SessionRecord[T_MsgPayload]] = {}
        self._session_lock = asyncio.Lock()
        self._inbound_task: asyncio.Task[None] | None = None
        self._outbound_task: asyncio.Task[None] | None = None

    async def run(self) -> None:
        """Run until inbound polling stops or the process is cancelled."""
        self._outbound_task = asyncio.create_task(self._process_outbound(), name="outbound")
        self._inbound_task = asyncio.create_task(self._poll_inbound(), name="inbound")
        try:
            await self._inbound_task
        finally:
            await self.shutdown()

    async def shutdown(self, timeout: float | None = 5.0) -> None:
        tasks = [task for task in (self._inbound_task, self._outbound_task) if task is not None]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._inbound_task = None
        self._outbound_task = None

        async with self._session_lock:
            sessions = [record.session for record in self._registered_sessions.values()]
        await asyncio.gather(*(session.stop(timeout=timeout) for session in sessions))

    async def process_incoming_msg(self, raw_data: Any) -> None:
        payload = self.parse_raw_data(raw_data)
        session_id = self.create_session_id(payload)
        incoming = self.get_input_msg_from_parsed_data(payload)

        should_start = False
        async with self._session_lock:
            if session_id not in self._registered_sessions:
                inbound_queue: asyncio.Queue[SessionInboundMsg] = asyncio.Queue(
                    maxsize=self._inbound_queue_maxsize
                )
                session = self._session_factory(
                    session_id,
                    inbound_queue,
                    self._outbound_queue,
                )
                self._registered_sessions[session_id] = SessionRecord(
                    session=session,
                    inbound_queue=inbound_queue,
                    msg_payload=payload,
                )
                should_start = True
            else:
                self._registered_sessions[session_id].msg_payload = payload
            session_record = self._registered_sessions[session_id]

        if should_start:
            await session_record.session.start()
        await session_record.inbound_queue.put(incoming)

    @abstractmethod
    def parse_raw_data(self, raw_data: Any) -> T_MsgPayload:
        """Validate and parse transport-specific inbound raw data."""

    @abstractmethod
    def create_session_id(self, payload: T_MsgPayload) -> str:
        """Derive a stable session id from parsed payload."""

    @abstractmethod
    def get_input_msg_from_parsed_data(
        self,
        payload: T_MsgPayload,
    ) -> SessionInboundMsg:
        """Build a session inbound message from parsed payload."""

    @abstractmethod
    async def _poll_inbound(self) -> None:
        """Poll network until cancelled; call :meth:`process_incoming_msg` per message."""

    @abstractmethod
    async def _send_outgoing(self, message: SessionOutboundMsg) -> None:
        """Send an outgoing message to the network."""

    async def _process_outbound(self) -> None:
        """Consume shared outbound queue and send to network."""
        try:
            while True:
                message = await self._outbound_queue.get()
                await self._send_outgoing(message)
        except asyncio.CancelledError:
            return
