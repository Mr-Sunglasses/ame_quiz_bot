from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Dict, Tuple

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, PollAnswer, CallbackQuery
from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.db.session import get_session_factory
from src.db.repo import QuizRepo, AttemptRepo

router = Router()

_active_attempts: Dict[int, dict] = {}
_group_sessions: Dict[Tuple[int, int], dict] = {}
_poll_to_ctx: Dict[str, dict] = {}


@router.message(CommandStart())
async def start_with_payload(message: Message, bot: Bot):
    parts = message.text.split(maxsplit=1)
    if len(parts) <= 1 or not parts[1].startswith("quiz_"):
        await message.answer(
            "👋 <b>Welcome to AME Quiz Bot!</b>\n\n"
            "Create and share quizzes right inside Telegram — solo or with your whole group.\n\n"
            "<b>Getting started:</b>\n"
            "  /newpolls — instantly post questions as polls (no saving)\n"
            "  /newquiz — create a saved quiz with a shareable link\n"
            "  /myquizzes — see all your quizzes\n\n"
            "Type /help for a full command reference."
        )
        return
    quiz_id = parts[1].split("_", 1)[1]
    if not quiz_id.isdigit():
        await message.answer("Invalid quiz link.")
        return
    qid = int(quiz_id)

    is_group = message.chat.type in {"group", "supergroup"}

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
            if not allowed and quiz.creator_id != message.from_user.id and not is_group:
                await message.answer(
                    "This quiz is private. You are not allowed to attempt it."
                )
                return
        qs = await qrepo.get_questions(qid)
        if len(qs) == 0:
            await message.answer("Quiz has no questions.")
            return

        if is_group:
            # Start or reset a group session
            key = (message.chat.id, qid)
            per_q = quiz.duration_minutes or 0
            _group_sessions[key] = {
                "mode": "group",
                "quiz_id": qid,
                "quiz_title": quiz.title,
                "chat_id": message.chat.id,
                "current_index": 0,
                "question_ids": [q.id for q in qs],
                "per_q_secs": per_q,
                "scores": {},  # user_id -> correct count
                "names": {},  # user_id -> display name
                "started_at": datetime.utcnow(),
                "last_results": None,
            }
            await message.answer(f"Starting quiz in group: {quiz.title}")
            await _group_next(bot, key, session_factory)
            return

        # Private 1:1 attempt flow
        prior = await arepo.get_user_latest_finished(qid, message.from_user.id)
        if prior:
            correct, wrong, missed = await arepo.get_attempt_stats(prior.id, len(qs))
            leaderboard = await arepo.leaderboard_first_attempts(qid)
            placement = None
            for idx, att in enumerate(leaderboard, start=1):
                if att.user_id == message.from_user.id and att.id == prior.id:
                    placement = idx
                    break
            total_attempts = len(leaderboard)
            place_line = (
                f"{placement}th place out of {total_attempts}."
                if placement
                else f"Out of {total_attempts}."
            )
            kb = InlineKeyboardBuilder()
            kb.button(text="Try again", callback_data=f"retry:{qid}")
            kb.button(
                text="Start quiz in group",
                url=f"https://t.me/{(await bot.me()).username}?startgroup=quiz_{qid}",
            )
            kb.button(
                text="Share quiz",
                url=f"https://t.me/{(await bot.me()).username}?start=quiz_{qid}",
            )
            await message.answer(
                (
                    f"🎲 Quiz '{quiz.title}'\n\n"
                    f"You already took this quiz. Your result on the leaderboard:\n\n"
                    f"✅ Correct – {correct}\n"
                    f"❌ Wrong – {wrong}\n"
                    f"⌛️ Missed – {missed}\n"
                    f"⏱ {(prior.finished_at - prior.started_at).total_seconds():.1f} sec\n\n"
                    f"{place_line}\n\n"
                    f"You can take this quiz again but it will not change your place on the leaderboard."
                ),
                reply_markup=kb.as_markup(),
            )

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
            "paused": False,
            "started_at": datetime.utcnow(),
            "correct": 0,
            "wrong": 0,
        }

        await message.answer("Starting quiz. Good luck!")
        await _send_next_question(bot, message.chat.id, attempt.id, session_factory)


async def _group_next(bot: Bot, key: Tuple[int, int], session_factory):
    st = _group_sessions.get(key)
    if not st:
        return
    idx = st["current_index"]
    session = session_factory()
    async with session as s:
        qrepo = QuizRepo(s)
        qs = await qrepo.get_questions(st["quiz_id"])
        if idx >= len(qs):
            await _group_finish(bot, key)
            return
        q = qs[idx]
        secs = st.get("per_q_secs", 0)
        timer_suffix = f" ⏳ {secs}s" if secs and secs > 0 else ""
        open_period = secs if isinstance(secs, int) and 5 <= secs <= 600 else None
        msg = await bot.send_poll(
            chat_id=st["chat_id"],
            question=(q.text[:280] + timer_suffix),
            options=q.options,
            type="quiz",
            correct_option_id=q.correct_index,
            is_anonymous=False,
            explanation=(q.reference[:200] if q.reference else None),
            explanation_parse_mode=None,
            open_period=open_period,
        )
        st["last_question_id"] = q.id
        if msg and msg.poll:
            _poll_to_ctx[msg.poll.id] = {"mode": "group", "key": key, "qid": q.id}
    # Auto-advance after timeout regardless of votes
    if st.get("per_q_secs", 0) > 0:

        async def timeout_then_next(expected_qid: int):
            await asyncio.sleep(st["per_q_secs"] + 1)
            cur = _group_sessions.get(key)
            if not cur or cur.get("last_question_id") != expected_qid:
                return
            cur["current_index"] += 1
            await _group_next(bot, key, session_factory)

        asyncio.create_task(timeout_then_next(q.id))


@router.poll_answer()
async def on_poll_answer(pa: PollAnswer, bot: Bot):
    # First, route by poll_id to group/private context
    ctx = _poll_to_ctx.get(pa.poll_id)
    if ctx and ctx.get("mode") == "group":
        key = ctx["key"]
        st = _group_sessions.get(key)
        if not st:
            return
        # Tally score for this user
        user = pa.user
        if pa.option_ids:
            # Determine correctness via last question id
            session_factory = get_session_factory()
            async with session_factory() as s:
                qrepo = QuizRepo(s)
                qs = await qrepo.get_questions(st["quiz_id"])
                q = next((qq for qq in qs if qq.id == st.get("last_question_id")), None)
                if not q:
                    return
                if pa.option_ids[0] == q.correct_index:
                    st["scores"][user.id] = st.get("scores", {}).get(user.id, 0) + 1
        # Save display name
        st["names"][user.id] = user.full_name or user.username or str(user.id)
        return

    # Otherwise, handle private attempt by attempt_id search via poll_id mapping (we now map it too)
    # Fallback to user-based mapping if needed
    attempt_id = None
    for aid, st in _active_attempts.items():
        if st.get("user_id") == pa.user.id:
            attempt_id = aid
            break
    if attempt_id is None:
        return
    state = _active_attempts[attempt_id]
    chat_id = state.get("chat_id")
    if chat_id is None or state.get("paused"):
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
            state["score"] += 1
            state["correct"] += 1
        else:
            await bot.send_message(chat_id, "Incorrect ❌")
            state["wrong"] += 1
        state["current_index"] += 1
    await _send_next_question(bot, chat_id, attempt_id, session_factory)


async def _group_finish(bot: Bot, key: Tuple[int, int]):
    st = _group_sessions.get(key)
    if not st:
        return
    # Build top-20 leaderboard
    scores = st.get("scores", {})
    names = st.get("names", {})
    # Sort by score desc
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    top20 = ranked[:20]
    lines = []
    for idx, (uid, sc) in enumerate(top20, start=1):
        name = names.get(uid, str(uid))
        lines.append(f"{idx}. {name} — {sc}")
    text = f"🎲 Quiz '{st.get('quiz_title', 'Quiz')}' — Group Results\n\n" + (
        "\n".join(lines) if lines else "No answers received."
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="Show result", callback_data=f"grpresult:{key[0]}:{key[1]}")
    await bot.send_message(st["chat_id"], text, reply_markup=kb.as_markup())
    # Save last results for callback
    st["last_results"] = {
        "ranked": ranked,
        "names": names,
    }


@router.callback_query(F.data.startswith("grpresult:"))
async def group_result(cb: CallbackQuery, bot: Bot):
    _, chat_id_s, quiz_id_s = cb.data.split(":", 2)
    key = (int(chat_id_s), int(quiz_id_s))
    st = _group_sessions.get(key)
    if not st or not st.get("last_results"):
        await cb.answer("No results available.")
        return
    ranked = st["last_results"]["ranked"]
    names = st["last_results"]["names"]
    lines = []
    for idx, (uid, sc) in enumerate(ranked, start=1):
        name = names.get(uid, str(uid))
        lines.append(f"{idx}. {name} — {sc}")
    # Send as a separate message to avoid long edit
    await bot.send_message(
        cb.message.chat.id, "Full results:\n" + "\n".join(lines[:100])
    )
    await cb.answer()


async def _send_next_question(bot: Bot, chat_id: int, attempt_id: int, session_factory):
    state = _active_attempts.get(attempt_id)
    if state is None or state.get("paused"):
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
        if msg and msg.poll:
            _poll_to_ctx[msg.poll.id] = {"mode": "private", "attempt_id": attempt_id}

    if state.get("per_q_secs", 0) > 0:

        async def timeout_and_pause(expected_qid: int):
            await asyncio.sleep(state["per_q_secs"] + 1)
            st = _active_attempts.get(attempt_id)
            if not st or st.get("last_question_id") != expected_qid:
                return
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
    total = len(state.get("question_ids", []))
    correct = state.get("correct", 0)
    wrong = state.get("wrong", 0)
    missed = max(0, total - (correct + wrong))
    duration_sec = max(
        1, int((datetime.utcnow() - state.get("started_at")).total_seconds())
    )
    async with session_factory() as session:
        arepo = AttemptRepo(session)
        await arepo.finish_attempt(attempt_id, correct)
        await session.commit()
        leaderboard = await arepo.leaderboard_first_attempts(state["quiz_id"])
        placement = None
        for idx, att in enumerate(leaderboard, start=1):
            if att.id == attempt_id:
                placement = idx
                break
        total_attempts = len(leaderboard)
    title = state.get("quiz_title", "Quiz")
    place_line = (
        f"{placement}th place out of {total_attempts}."
        if placement
        else f"Out of {total_attempts}."
    )
    await bot.send_message(
        chat_id,
        (
            f"🎲 Quiz '{title}'\n\n"
            f"Your result on the leaderboard:\n\n"
            f"✅ Correct – {correct}\n"
            f"❌ Wrong – {wrong}\n"
            f"⌛️ Missed – {missed}\n"
            f"⏱ {duration_sec:.1f} sec\n\n"
            f"{place_line}"
        ),
    )
    _active_attempts.pop(attempt_id, None)
