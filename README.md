# Calorie tracker Telegram bot

Personal calorie logging bot: meals, edits, goals, and reports. Responses are short Jinja2 templates; the LLM is used only for structured intent parsing.

## Setup

1. Create a virtualenv and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and set variables.

3. Run:

   ```bash
   python main.py
   ```

## Environment

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_TOKEN` | yes | Bot token from [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | no | Chat ID for scheduled weekly/monthly reports |
| `LLM_MODEL` | no | e.g. `ollama/llama3.2` or `gpt-4o-mini` |
| `OLLAMA_BASE_URL` | no | Default `http://127.0.0.1:11434` |
| `OPENAI_API_KEY` | if using OpenAI | API key for cloud models |
| `USDA_API_KEY` | no | Improves food lookup after Open Food Facts |
| `TZ` | no | IANA timezone for logs and scheduler |

## Docker

```bash
docker compose up --build -d
```

Persisted data: `./data/calorie_data.json` (mounted volume).

## Notes

- **Dependencies:** `aiogram==3.13.0` and `pydantic==2.10.x` cannot be installed together (aiogram 3.13 caps pydantic below 2.9). This repo uses `aiogram==3.20.0` with `pydantic` 2.10.x so the stack resolves cleanly.
- Data file: `data/calorie_data.json` (created automatically). Backups: `calorie_data.json.bak` on each save.
| `TELEGRAM_CHAT_ID` | no | Chat ID for scheduled weekly/monthly reports |
| `LLM_MODEL` | no | e.g. `ollama/llama3.2` or `gpt-4o-mini` |
| `OLLAMA_BASE_URL` | no | Default `http://127.0.0.1:11434` |
| `OPENAI_API_KEY` | if using OpenAI | API key for cloud models |
| `USDA_API_KEY` | no | Improves food lookup after Open Food Facts |
| `TZ` | no | IANA timezone for logs and scheduler |

## Docker

```bash
docker compose up --build -d
```

Persisted data: `./data/calorie_data.json` (mounted volume).

## Notes

- **Dependencies:** `aiogram==3.13.0` and `pydantic==2.10.x` cannot be installed together (aiogram 3.13 caps pydantic below 2.9). This repo uses `aiogram==3.20.0` with `pydantic` 2.10.x so the stack resolves cleanly.
- Data file: `data/calorie_data.json` (created automatically). Backups: `calorie_data.json.bak` on each save.
