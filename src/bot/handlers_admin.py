from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.db.session import get_session_factory
from src.db.repo import QuizRepo

router = Router()


@router.message(Command("myquizzes"))
async def myquizzes(message: Message):
    async with get_session_factory()() as session:
        repo = QuizRepo(session)
        quizzes = await repo.list_user_quizzes(message.from_user.id)
        if not quizzes:
            await message.answer("You have no quizzes.")
            return
        lines = [f"#{q.id} — {q.title} ({'public' if q.public_flag else 'private'})" for q in quizzes]
        await message.answer("\n".join(lines[:50]))


@router.message(Command("deletequiz"))
async def deletequiz(message: Message):
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Usage: /deletequiz <id>")
        return
    qid = int(parts[1])
    async with get_session_factory()() as session:
        repo = QuizRepo(session)
        ok = await repo.delete_quiz_if_owner(qid, message.from_user.id)
        if not ok:
            await message.answer("Not found or you are not the owner.")
            return
        await session.commit()
        await message.answer("Deleted.")
