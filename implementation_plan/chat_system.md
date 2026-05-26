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