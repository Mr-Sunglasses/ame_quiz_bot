from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("ping"))
async def ping(message: Message):
    await message.answer("pong")


@router.message()
async def fallback(message: Message):
    # Only reply in private chats to avoid group noise
    if message.chat.type == "private":
        await message.answer("Hi! Use /newquiz to create a quiz or /start for help.")
