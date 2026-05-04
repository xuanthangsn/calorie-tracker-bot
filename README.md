# Calorie tracker Telegram bot

Personal calorie logging bot: meals, edits, goals, and reports.

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
| `GEMINI_API_KEY` | yes | API key for LLM call |
| `MEMORY` | no | memory root folder, local file system that agent has access to |

## Docker

```bash
docker compose up --build -d
```