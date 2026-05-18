# Telegram dispatcher

Concrete `TelegramDispatcher` extends [`chat/dispatcher.py`](../chat/dispatcher.py) `BaseDispatcher`. See [`chat_system.md`](chat_system.md) for the overall chat architecture.

## Concurrency

| Layer | Model |
|--------|--------|
| Entire chat stack | **Single asyncio event loop** |
| Telegram I/O | `start_polling`, `await send_message` on same loop |
| Dispatcher | Outbound consumer task; inbound: aiogram handlers call `_process_inbound_msg` directly |
| Per-chat session | One `asyncio.Task` per `session_id`; `await inbox.get()` + `await _handle_request` |

No `threading` or `queue.Queue` in the chat layer.

## Construction

```python
TelegramDispatcher(bot_token: str, session_factory, *, parse_mode=ParseMode.HTML)
```

- `name = "telegram"` class attribute; `get_name()` returns it
- `bot_token` is required (non-empty); callers pass `config.TELEGRAM_TOKEN` from `main.py`.
- `session_factory(session_id, send_reply: SendReplyCallback) -> BaseChatSession`
- Dispatcher builds `send_reply` per session; sessions do not see the global outbox queue

## Inbound pipeline

All inbound messages flow through `BaseDispatcher._process_inbound_msg(msg_payload)`:

1. `session_id = _generate_session_id(msg_payload)` (abstract, per channel)
2. `_route_msg(session_id, msg_payload)` — session registry + `_to_incoming_message` → session inbox

Network I/O (aiogram handlers) builds `msg_payload` and calls `await _process_inbound_msg(msg_payload)`. `_poll_inbound` only runs `start_polling`.

### Telegram `msg_payload`

Built in the aiogram handler after skip rules (no text / blank → do not call `_process_inbound_msg`):

```python
{"chat_id": int, "text": str, "message_id": int}
```

- `_generate_session_id`: `str(msg_payload["chat_id"])`
- `_to_incoming_message`: `IncomingMessage(session_id, msg_payload["text"])`

Parsing helpers (`_text_from_message`, etc.) stay in the handler path.

## Outbound

- `chat_id = int(message.session_id)`; log and drop on invalid id

## Entrypoint

```python
asyncio.run(main())  # await dispatcher.run()
```
