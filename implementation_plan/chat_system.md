# Plan: Decoupled Message Handling Architecture

> **Current code:** single **asyncio** event loop — `asyncio.Queue`, `asyncio.Lock`, `asyncio.create_task` (see [`chat/dispatcher.py`](../chat/dispatcher.py), [`chat/session.py`](../chat/session.py), [`telegram_dispatcher.md`](telegram_dispatcher.md)). Dispatcher injects `inbound_queue`/`outbound_queue` into sessions; sessions only handle messages.

High-level components managing the flow of messages between the external network and the internal system. The components communicate entirely asynchronously via message passing and have no direct method-call coupling or awareness of each other's internal logic.

---

## `Dispatcher`

**Behavior:** Acts as the centralized, stateless gateway for the system. It handles all network I/O, constantly polling for incoming messages, routing them to the appropriate isolated session, and forwarding outgoing messages back to the external network.

**Implementation requirements:**

* **Shared Outbound Queue:** Maintain a single **bounded** shared `outbound_queue` to collect outgoing session messages from all active sessions.
* **Session Registry:** Maintain `registered_session: dict[session_id, SessionRecord[T_MsgPayload]]`.
* **Parsing:** Validate raw transport data with `parse_raw_data(raw_data) -> T_MsgPayload`.
* **Session ID Strategy:** Derive session ID via `create_session_id(payload)`.
* **Input Mapping:** Convert parsed payload to `SessionInboundMsg` via `get_input_msg_from_parsed_data(payload)`.
* **Routing Logic:** In `process_incoming_msg(raw_data)`, create session record lazily, inject `inbound_queue`/shared `outbound_queue`, `start()` session once, then enqueue inbound message.
* **Outbound Loop:** Consume shared `outbound_queue`, execute concrete network send operation.
* **Shutdown:** Support cooperative **graceful shutdown** with a documented `shutdown` entrypoint and joinable tasks.

**Implementation example:**
```code
import queue
import threading
from abc import ABC, abstractmethod

class BaseDispatcher(ABC):
    def __init__(self):
        # Bounded global outbox — maxsize must be explicit (tune via config in real code).
        self.global_outbox = queue.Queue(maxsize=256)
        self.active_sessions: dict[str, 'BaseChatSession'] = {}

    def start(self):
        """Starts background I/O loops."""
        threading.Thread(target=self.poll_inbound, daemon=True).start()
        threading.Thread(target=self.process_outbound, daemon=True).start()

    def route_incoming(self, session_id: str, text: str):
        """Routes message to existing session or creates a new one."""
        if session_id not in self.active_sessions:
            self.active_sessions[session_id] = self.create_session(session_id, self.global_outbox)
        self.active_sessions[session_id].inbox.put(IncomingMessage(session_id, text))

    @abstractmethod
    def create_session(self, session_id: str, outbox: queue.Queue) -> 'BaseChatSession':
        pass

    @abstractmethod
    def poll_inbound(self):
        """Loop until shutdown: poll network -> call self.route_incoming()"""
        pass

    @abstractmethod
    def process_outbound(self):
        """Loop until shutdown: block on self.global_outbox.get() -> send to network"""
        pass
```

_Illustration only: add stop events, `shutdown()`, lock-safe routing, and session inbox bounds as in sections below._

## `Session`

**Behavior:** Acts as the isolated, active manager for a single chat's lifecycle. It operates completely unaware of the network layer, responding asynchronously to events triggered by messages dropped into its private mailbox by the Dispatcher.

**Implementation requirements:**

* **Inbound Queue:** Receive an injected **bounded** `inbound_queue` from the dispatcher.
* **Outbound Queue:** Receive an injected shared **bounded** `outbound_queue` from the dispatcher.
* **Active Worker Task:** Spin up a dedicated async worker task via `start()`.
* **Shutdown:** Session worker must participate in **graceful shutdown** (stop signal or sentinel) so threads can join (see [Graceful shutdown](#graceful-shutdown)).
* **Worker Loop:** `poll_incoming_msg` blocks on `inbound_queue.get()`, calls `handle_msg`, then enqueues `SessionOutboundMsg` to `outbound_queue`.
* **Request Handler:** Session only implements `handle_msg(msg)`; it knows nothing about dispatcher internals.
* **Send Mechanism:** Session creates outbound envelopes itself including current timestamp.

**Implementation example**
```code
import queue
import threading
from abc import ABC, abstractmethod

class BaseChatSession(ABC):
    def __init__(self, session_id: str, global_outbox: queue.Queue):
        self.session_id = session_id
        self.global_outbox = global_outbox
        self.inbox = queue.Queue(maxsize=64)  # bounded per-session inbox
        
        # Start private worker thread
        threading.Thread(target=self._worker_loop, daemon=True).start()

    def _worker_loop(self):
        """Blocks until a message arrives or shutdown is requested."""
        while True:
            message: IncomingMessage = self.inbox.get(block=True)
            self.handle_request(message)

    def send_reply(self, text: str):
        """Fire and forget to the global outbox."""
        self.global_outbox.put(OutgoingMessage(self.session_id, text))

    @abstractmethod
    def handle_request(self, message: IncomingMessage):
        """
        Do whatever to handle the request, for example:
        1. Fetch context from DB repository.
        2. Instantiate the Stateless Task.
        3. Execute Task and capture result.
        4. Save result to DB repository.
        5. Call self.send_reply(result).
        """
        pass
```

_Illustration only: the worker `while True` must be replaced with shutdown-aware logic as in [Graceful shutdown](#graceful-shutdown)._

## `Data envelopes` (The contracts)
Standardized payloads used between components without exposing dispatcher internals.

```code
from dataclasses import dataclass

@dataclass
class SessionInboundMsg:
    message: str
    time: datetime

@dataclass
class SessionOutboundMsg:
    session_id: str
    message: str
    time: datetime
```
---

## Generic dispatcher payload contract

Each concrete dispatcher defines a typed payload for validated incoming network data.

```code
class BaseMessagePayload(ABC): ...
T_MsgPayload = TypeVar("T_MsgPayload", bound=BaseMessagePayload)

@dataclass
class SessionRecord(Generic[T_MsgPayload]):
    session: BaseChatSession
    inbound_queue: asyncio.Queue[SessionInboundMsg]
    msg_payload: T_MsgPayload
```