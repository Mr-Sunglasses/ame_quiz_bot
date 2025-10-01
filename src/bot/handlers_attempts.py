from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, PollAnswer
from aiogram import Bot

from src.db.session import get_session_factory
from src.db.repo import QuizRepo, AttemptRepo

router = Router()

# In-memory attempt state cache (MVP). For production, consider persistent or redis-backed.
_active_attempts: Dict[int, dict] = {}


@router.message(CommandStart())
async def start_with_payload(message: Message, bot: Bot):
    parts = message.text.split(maxsplit=1)
    if len(parts) <= 1 or not parts[1].startswith("quiz_"):
        return
    quiz_id = parts[1].split("_", 1)[1]
    if not quiz_id.isdigit():
        await message.answer("Invalid quiz link.")
        return
    qid = int(quiz_id)

    session_factory = get_session_factory()
    async with session_factory() as session:
        qrepo = QuizRepo(session)
        arepo = AttemptRepo(session)
        quiz = await qrepo.get_quiz(qid)
        if quiz is None:
            await message.answer("Quiz not found.")
            return
        # Enforce visibility
        if not quiz.public_flag:
            allowed = await qrepo.is_user_allowed(qid, message.from_user.id)
            if not allowed and quiz.creator_id != message.from_user.id:
                await message.answer("This quiz is private. You are not allowed to attempt it.")
                return
        qs = await qrepo.get_questions(qid)
        if len(qs) == 0:
            await message.answer("Quiz has no questions.")
            return
        attempt = await arepo.create_attempt(qid, message.from_user.id)
        await session.commit()

        start_time = datetime.utcnow()
        deadline = None
        if quiz.duration_minutes and quiz.duration_minutes > 0:
            deadline = start_time + timedelta(minutes=quiz.duration_minutes)

        _active_attempts[attempt.id] = {
            "quiz_id": qid,
            "user_id": message.from_user.id,
            "current_index": 0,
            "question_ids": [q.id for q in qs],
            "start_time": start_time,
            "deadline": deadline,
            "score": 0,
            "chat_id": message.chat.id,
        }

        await message.answer("Starting quiz. Good luck!")
        await _send_next_question(bot, message.chat.id, attempt.id, session_factory)


async def _send_next_question(bot: Bot, chat_id: int, attempt_id: int, session_factory):
    state = _active_attempts.get(attempt_id)
    if state is None:
        return
    # Check deadline
    if state.get("deadline") and datetime.utcnow() >= state["deadline"]:
        await _finish_attempt(bot, chat_id, attempt_id, session_factory, time_up=True)
        return

    idx = state["current_index"]
    session = session_factory()
    async with session as s:
        qrepo = QuizRepo(s)
        qs = await qrepo.get_questions(state["quiz_id"])
        if idx >= len(qs):
            await _finish_attempt(bot, chat_id, attempt_id, session_factory)
            return
        q = qs[idx]
        # Remaining time info (as separate message for clarity)
        if state.get("deadline"):
            remaining = int((state["deadline"] - datetime.utcnow()).total_seconds())
            if remaining < 0:
                remaining = 0
            mins = remaining // 60
            secs = remaining % 60
            await bot.send_message(chat_id, f"Time left: {mins}:{secs:02d}")
        await bot.send_poll(
            chat_id=chat_id,
            question=q.text[:300],
            options=q.options,
            type="quiz",
            correct_option_id=q.correct_index,
            is_anonymous=False,
            explanation=q.reference[:200] if q.reference else None,
            explanation_parse_mode=None,
        )
        # Store mapping from user poll progress
        state["last_question_id"] = q.id


@router.poll_answer()
async def on_poll_answer(pa: PollAnswer, bot: Bot):
    user_id = pa.user.id
    # Find the active attempt for this user
    attempt_id = None
    for aid, st in _active_attempts.items():
        if st["user_id"] == user_id:
            attempt_id = aid
            break
    if attempt_id is None:
        return
    state = _active_attempts[attempt_id]
    chat_id = state.get("chat_id")
    if chat_id is None:
        return
    session_factory = get_session_factory()
    async with session_factory() as session:
        qrepo = QuizRepo(session)
        arepo = AttemptRepo(session)
        qs = await qrepo.get_questions(state["quiz_id"])
        q = next((qq for qq in qs if qq.id == state.get("last_question_id")), None)
        if q is None:
            return
        chosen = pa.option_ids[0] if pa.option_ids else -1
        is_correct = chosen == q.correct_index
        await arepo.upsert_answer(attempt_id, q.id, chosen, is_correct)
        await session.commit()
        # Immediate feedback
        if is_correct:
            await bot.send_message(chat_id, "Correct ✅")
        else:
            await bot.send_message(chat_id, f"Incorrect ❌ — correct: {q.options[q.correct_index]}")
        if q.reference:
            await bot.send_message(chat_id, f"Ref: {q.reference}")
        if is_correct:
            state["score"] += 1
        state["current_index"] += 1
    await _send_next_question(bot, chat_id, attempt_id, session_factory)


async def _finish_attempt(bot: Bot, chat_id: int, attempt_id: int, session_factory, time_up: bool = False):
    state = _active_attempts.get(attempt_id)
    if state is None:
        return
    score = state.get("score", 0)
    total = len(state.get("question_ids", []))
    percent = (score * 100) // total if total else 0
    async with session_factory() as session:
        arepo = AttemptRepo(session)
        await arepo.finish_attempt(attempt_id, score)
        await session.commit()
    await bot.send_message(chat_id, f"Finished! Score: {score}/{total} ({percent}%)." + (" Time's up." if time_up else ""))
    _active_attempts.pop(attempt_id, None)
