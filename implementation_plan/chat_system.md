# Plan: Decoupled Message Handling Architecture

High-level components managing the flow of messages between the external network and the internal system. The components communicate entirely asynchronously via thread-safe queues (message passing) and have no direct method-call coupling or awareness of each other's internal logic.

---

## `Dispatcher`

**Behavior:** Acts as the centralized, stateless gateway for the system. It handles all network I/O, constantly polling for incoming messages, routing them to the appropriate isolated session, and forwarding outgoing messages back to the external network.

**Implementation requirements:**

* **Global Outbox:** Maintain a single **bounded** thread-safe queue to collect outgoing messages from all active sessions (see [Bounded queues](#bounded-queues-backpressure)).
* **Session Registry:** Maintain a dictionary or map tracking active sessions by their unique session ID.
* **Inbound Loop:** Run a dedicated background thread that continuously polls the external chat API for new messages.
* **Routing Logic:** Extract the session ID from incoming messages. If the session exists, push the message into its private inbox. If it does not exist, instantiate a new session, register it, and then push the message.
* **Outbound Loop:** Run a dedicated background thread that continuously blocks on the global outbox, popping messages as they arrive and executing the actual network send operations.
* **Shutdown:** Support cooperative **graceful shutdown** with a documented `shutdown` entrypoint and joinable loop threads (see [Graceful shutdown](#graceful-shutdown)).

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

* **Private Inbox:** Maintain a dedicated **bounded** thread-safe queue to receive incoming messages routed specifically to this session (see [Bounded queues](#bounded-queues-backpressure)).
* **Outbox Reference:** Hold a reference to the Dispatcher's global outbox in order to pass outgoing messages back up the chain.
* **Active Worker Thread:** Automatically spin up a dedicated background worker thread immediately upon instantiation.
* **Shutdown:** Session worker must participate in **graceful shutdown** (stop signal or sentinel) so threads can join (see [Graceful shutdown](#graceful-shutdown)).
* **Worker Loop:** Implement a loop that blocks until a new message arrives or until **shutdown** is requested (see [Graceful shutdown](#graceful-shutdown)); must not spin CPU.
* **Request Handler:** Implement a method triggered by the worker loop to process the popped message, load any necessary historical context, execute the core reasoning logic, and determine the response.
* **Send Mechanism:** Implement a fire-and-forget method to package the final response and drop it into the global outbox.

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
Standardized payloads used to pass data between threads without exposing component internals

```code
from dataclasses import dataclass

@dataclass
class IncomingMessage:
    session_id: str
    text: str

@dataclass
class OutgoingMessage:
    session_id: str
    text: str
```
---