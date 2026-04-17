"""Minimal Telegram bot handlers."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer("Bot is running. Send any text and I will echo it.")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer("Commands: /start, /help")


@router.message(F.text)
async def on_text(message: Message) -> None:
    if not message.text:
        return
    await message.answer(f"You said: {message.text}")
