from __future__ import annotations

import asyncio
from typing import Dict

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, PollAnswer, CallbackQuery
from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.db.session import get_session_factory
from src.db.repo import QuizRepo, AttemptRepo

router = Router()

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
        if not quiz.public_flag:
            allowed = await qrepo.is_user_allowed(qid, message.from_user.id)
            if not allowed and quiz.creator_id != message.from_user.id:
                await message.answer(
                    "This quiz is private. You are not allowed to attempt it."
                )
                return
        qs = await qrepo.get_questions(qid)
        if len(qs) == 0:
            await message.answer("Quiz has no questions.")
            return
        attempt = await arepo.create_attempt(qid, message.from_user.id)
        await session.commit()

        per_question_seconds = quiz.duration_minutes or 0
        _active_attempts[attempt.id] = {
            "quiz_id": qid,
            "quiz_title": quiz.title,
            "user_id": message.from_user.id,
            "current_index": 0,
            "question_ids": [q.id for q in qs],
            "score": 0,
            "chat_id": message.chat.id,
            "per_q_secs": per_question_seconds,
            "pending_poll_id": None,
            "paused": False,
        }

        await message.answer("Starting quiz. Good luck!")
        await _send_next_question(bot, message.chat.id, attempt.id, session_factory)


async def _send_next_question(bot: Bot, chat_id: int, attempt_id: int, session_factory):
    state = _active_attempts.get(attempt_id)
    if state is None:
        return
    if state.get("paused"):
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
        secs = state.get("per_q_secs", 0)
        timer_suffix = f" ⏳ {secs}s" if secs and secs > 0 else ""
        open_period = secs if isinstance(secs, int) and 5 <= secs <= 600 else None
        msg = await bot.send_poll(
            chat_id=chat_id,
            question=(q.text[:280] + timer_suffix),
            options=q.options,
            type="quiz",
            correct_option_id=q.correct_index,
            is_anonymous=False,
            explanation=(q.reference[:200] if q.reference else None),
            explanation_parse_mode=None,
            open_period=open_period,
        )
        state["last_question_id"] = q.id
        state["pending_poll_id"] = msg.poll.id if msg and msg.poll else None

    if state.get("per_q_secs", 0) > 0:

        async def timeout_and_pause(expected_qid: int):
            await asyncio.sleep(state["per_q_secs"] + 1)
            st = _active_attempts.get(attempt_id)
            if not st or st.get("last_question_id") != expected_qid:
                return
            # Pause instead of auto-advancing
            st["paused"] = True
            title = st.get("quiz_title", "Quiz")
            kb = InlineKeyboardBuilder()
            kb.button(text="▶️ Resume", callback_data=f"resume:{attempt_id}")
            kb.button(text="⏹ Stop", callback_data=f"stop:{attempt_id}")
            await bot.send_message(
                chat_id,
                f"⏸ The quiz '{title}' was paused because you stopped answering.",
                reply_markup=kb.as_markup(),
            )

        asyncio.create_task(timeout_and_pause(q.id))


@router.poll_answer()
async def on_poll_answer(pa: PollAnswer, bot: Bot):
    user_id = pa.user.id
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
    if state.get("paused"):
        # ignore late answers during paused state
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
        if is_correct:
            await bot.send_message(chat_id, "Correct ✅")
        else:
            await bot.send_message(chat_id, "Incorrect ❌")
        if is_correct:
            state["score"] += 1
        state["current_index"] += 1
    await _send_next_question(bot, chat_id, attempt_id, session_factory)


@router.callback_query(F.data.startswith("resume:"))
async def resume_quiz(cb: CallbackQuery, bot: Bot):
    attempt_id = int(cb.data.split(":", 1)[1])
    st = _active_attempts.get(attempt_id)
    if not st or st.get("user_id") != cb.from_user.id:
        await cb.answer()
        return
    st["paused"] = False
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.answer("Resuming…")
    await _send_next_question(
        bot, cb.message.chat.id, attempt_id, get_session_factory()
    )


@router.callback_query(F.data.startswith("stop:"))
async def stop_quiz(cb: CallbackQuery, bot: Bot):
    attempt_id = int(cb.data.split(":", 1)[1])
    st = _active_attempts.get(attempt_id)
    if not st or st.get("user_id") != cb.from_user.id:
        await cb.answer()
        return
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.answer("Stopped.")
    await _finish_attempt(bot, cb.message.chat.id, attempt_id, get_session_factory())


async def _finish_attempt(
    bot: Bot, chat_id: int, attempt_id: int, session_factory, time_up: bool = False
):
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
    await bot.send_message(chat_id, f"Finished! Score: {score}/{total} ({percent}%).")
    _active_attempts.pop(attempt_id, None)
