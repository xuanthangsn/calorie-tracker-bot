"""Isolated per-chat session base."""

from __future__ import annotations

import queue
import threading
from abc import ABC, abstractmethod
from queue import Queue

from chat.messages import IncomingMessage, OutgoingMessage

from enum import Enum, auto

class ChatSessionState(Enum):
    PENDING = auto()
    ACTIVE = auto()

class BaseChatSession(ABC):
    """One chat: private inbox, worker thread, replies via dispatcher global outbox."""

    def __init__(self, session_id: str, global_outbox: Queue[OutgoingMessage]) -> None:
        self.session_id = session_id
        self.global_outbox = global_outbox
        self.inbox: Queue[IncomingMessage] = queue.Queue()

        self._worker = threading.Thread(target=self._worker_loop, daemon=True)

    def start(self) -> None:
        self._worker.start()

    def stop(self, timeout: float | None = None) -> None:
        self._worker.join(timeout)

    def _worker_loop(self) -> None:
        while True:
            message = self.inbox.get(block=True)
            self.handle_request(message)

    def _send_reply(self, text: str) -> None:
        self.global_outbox.put(OutgoingMessage(self.session_id, text))

    @abstractmethod
    def _handle_request(self, message: IncomingMessage) -> None:
        """Process one inbound message; use :meth:`send_reply` to respond."""
