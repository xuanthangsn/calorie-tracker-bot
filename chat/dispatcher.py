"""Central gateway: registry, global outbox, inbound/outbound background loops."""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from queue import Queue

from chat.messages import IncomingMessage, OutgoingMessage
from chat.session import BaseChatSession


class BaseDispatcher(ABC):
    """Thread-safe global outbox, session map, and abstract I/O hooks."""

    def __init__(self) -> None:
        self._global_outbox: Queue[OutgoingMessage] = Queue()
        self._active_sessions: dict[str, BaseChatSession] = {}
        self._session_lock = threading.Lock()

    def start(self) -> None:
        threading.Thread(target=self._poll_inbound, daemon=True).start()
        threading.Thread(target=self._process_outbound, daemon=True).start()

    def _route_incoming(self, session_id: str, text: str) -> None:
        with self._session_lock:
            if session_id not in self._active_sessions:
                session = self._create_session(session_id)
                session.start()
                self._active_sessions[session_id] = session
            session = self._active_sessions[session_id]
        session.inbox.put(IncomingMessage(session_id, text))

    @abstractmethod
    def _create_session(self, session_id: str) -> BaseChatSession:
        """Create a session for the given session id."""

    @abstractmethod
    def _create_session_id(self, message_paypload: dict) -> str:
        """Create a session id from the message payload."""
        
    @abstractmethod
    def _poll_inbound(self) -> None:
        """Blocking loop: poll network, then :meth:`_route_incoming`."""

    @abstractmethod
    def _process_outbound(self) -> None:
        """Blocking loop: read from :attr:`_global_outbox`, send to network."""
