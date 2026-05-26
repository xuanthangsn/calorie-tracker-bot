# Telegram dispatcher

Concrete `TelegramDispatcher` extends [`chat/dispatcher.py`](../chat/dispatcher.py) `BaseDispatcher`. See [`chat_system.md`](chat_system.md) for the overall chat architecture.

## Concurrency

| Layer | Model |
|--------|--------|
| Entire chat stack | **Single asyncio event loop** |
| Telegram I/O | `start_polling`, `await send_message` on same loop |
| Dispatcher | Outbound consumer task; inbound: aiogram handlers call `process_incoming_msg` directly |
| Per-chat session | One `asyncio.Task` per `session_id`; `await inbound_queue.get()` + `await handle_msg` |

No `threading` or `queue.Queue` in the chat layer.

## Construction

```python
TelegramDispatcher(bot_token: str, session_factory, *, parse_mode=ParseMode.HTML)
```

- `name = "telegram"` class attribute; `get_name()` returns it
- `bot_token` is required (non-empty); callers pass `config.TELEGRAM_TOKEN` from `main.py`.
- `session_factory(session_id, inbound_queue, outbound_queue) -> BaseChatSession`
- Dispatcher owns queue creation and injects both queues into each created session

## Inbound pipeline

All inbound messages flow through `BaseDispatcher.process_incoming_msg(raw_data)`:

1. `payload = parse_raw_data(raw_data)` (typed `TelegramMessagePayload`)
2. `session_id = create_session_id(payload)`
3. `incoming = get_input_msg_from_parsed_data(payload)`
4. `process_incoming_msg` creates/starts session lazily and enqueues to session `inbound_queue`

Network I/O (aiogram handlers) passes raw `Message` to `await process_incoming_msg(message)`. `_poll_inbound` only runs `start_polling`.

### Telegram `msg_payload`

Parsed by `parse_raw_data` after skip rules (no text / blank → do not call `process_incoming_msg`):

```python
TelegramMessagePayload(chat_id: int, text: str, message_id: int, time: datetime)
```

- `create_session_id`: `str(payload.chat_id)`
- `get_input_msg_from_parsed_data`: `SessionInboundMsg(message=payload.text, time=payload.time)`

Parsing helpers (`_text_from_message`, etc.) stay in the handler path.

## Outbound

- `chat_id = int(message.session_id)`; log and drop on invalid id
- outbound body is `message.message`

## Entrypoint

```python
asyncio.run(main())  # await dispatcher.run()
```
