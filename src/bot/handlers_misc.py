from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()

HELP_TEXT = (
    "📋 <b>AME Quiz Bot — Command Reference</b>\n\n"

    "<b>Quick polls (no saving)</b>\n"
    "  /newpolls — instantly post questions as Telegram polls\n"
    "  Great for sharing questions in a channel or group\n\n"

    "<b>Creating saved quizzes</b>\n"
    "  /newquiz — create a quiz with a shareable link\n"
    "  /myquizzes — list all quizzes you've created\n"
    "  /deletequiz &lt;id&gt; — delete one of your quizzes\n\n"

    "<b>Taking a quiz</b>\n"
    "  Open a quiz link or send <code>/start quiz_&lt;id&gt;</code>\n"
    "  Works in private chat or group — just forward the link\n\n"

    "<b>During a quiz</b>\n"
    "  Answer each poll question before the timer runs out\n"
    "  If you stop answering you'll be paused — tap <b>Resume</b> to continue\n"
    "  Your first attempt counts for the leaderboard\n\n"

    "<b>Question format</b>\n"
    "<pre>Q. Question text\n"
    "(A) Option 1\n"
    "(B) Option 2\n"
    "(C) Option 3\n"
    "(D) Option 4\n"
    "Ans - B\n"
    "Reference - source</pre>\n\n"

    "<b>Other</b>\n"
    "  /help — show this message\n"
    "  /ping — check if the bot is alive\n"
)


@router.message(Command("help"))
async def help_command(message: Message):
    await message.answer(HELP_TEXT)


@router.message(Command("ping"))
async def ping(message: Message):
    await message.answer("pong")


@router.message()
async def fallback(message: Message):
    # Only reply in private chats to avoid group noise
    if message.chat.type == "private":
        await message.answer("Use /newquiz to create a quiz or /help to see all commands.")
