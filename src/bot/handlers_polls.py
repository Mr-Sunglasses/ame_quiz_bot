from __future__ import annotations

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot.states import NewPollsStates
from src.parser.quiz_parser import parse_single_block, parse_bulk, ParsedQuestion

router = Router()


def _settings_summary(is_quiz: bool, is_anonymous: bool) -> str:
    kind = "Quiz (shows correct answer)" if is_quiz else "Regular poll"
    anon = "Anonymous" if is_anonymous else "Public"
    return f"Type: {kind} · {anon}"


@router.message(Command("newpolls"))
async def newpolls(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(NewPollsStates.waiting_poll_type)
    await state.update_data(count=0)
    kb = InlineKeyboardBuilder()
    kb.button(text="🧠 Quiz (shows correct answer)", callback_data="polltype:quiz")
    kb.button(text="📊 Regular poll", callback_data="polltype:regular")
    kb.adjust(1)
    await message.answer("Choose poll type:", reply_markup=kb.as_markup())


@router.callback_query(NewPollsStates.waiting_poll_type, F.data.startswith("polltype:"))
async def polls_type_selected(cb: CallbackQuery, state: FSMContext):
    is_quiz = cb.data.split(":")[1] == "quiz"
    await state.update_data(is_quiz=is_quiz)
    await state.set_state(NewPollsStates.waiting_anonymous)
    await cb.message.edit_reply_markup(reply_markup=None)
    kb = InlineKeyboardBuilder()
    kb.button(text="🔒 Anonymous", callback_data="pollanon:yes")
    kb.button(text="👁 Public (non-anonymous)", callback_data="pollanon:no")
    kb.adjust(1)
    await cb.message.answer("Anonymous voting?", reply_markup=kb.as_markup())
    await cb.answer()


@router.callback_query(NewPollsStates.waiting_anonymous, F.data.startswith("pollanon:"))
async def polls_anonymous_selected(cb: CallbackQuery, state: FSMContext):
    is_anonymous = cb.data.split(":")[1] == "yes"
    await state.update_data(is_anonymous=is_anonymous)
    await state.set_state(NewPollsStates.waiting_mode)
    await cb.message.edit_reply_markup(reply_markup=None)
    data = await state.get_data()
    summary = _settings_summary(data["is_quiz"], is_anonymous)
    await cb.message.answer(
        f"✅ {summary}\n\n"
        "Send questions one-by-one or paste all at once?\n"
        "Reply <b>single</b> or <b>bulk</b>."
    )
    await cb.answer()


@router.message(NewPollsStates.waiting_mode, F.text.lower().in_({"single", "bulk"}))
async def polls_mode_selected(message: Message, state: FSMContext):
    mode = message.text.lower()
    await state.update_data(mode=mode)
    if mode == "single":
        await state.set_state(NewPollsStates.waiting_single_question)
        await message.answer(
            "Send each question and I'll post a poll immediately.\n"
            "Send /done when you're finished."
        )
    else:
        await state.set_state(NewPollsStates.waiting_bulk_content)
        await message.answer("Paste all your questions, then send /parse.")


@router.message(NewPollsStates.waiting_single_question, F.text == "/done")
async def polls_single_done(message: Message, state: FSMContext):
    data = await state.get_data()
    count = data.get("count", 0)
    await state.clear()
    if count == 0:
        await message.answer("No questions were sent.")
    else:
        await message.answer(f"Done! Posted {count} poll{'s' if count != 1 else ''}.")


@router.message(NewPollsStates.waiting_single_question)
async def polls_single_question(message: Message, state: FSMContext, bot: Bot):
    pq, err = parse_single_block(message.text)
    if err:
        await message.answer(f"Could not parse question.\nError: {err.message}")
        return
    assert pq is not None
    data = await state.get_data()
    await _send_poll(bot, message.chat.id, pq, data["is_quiz"], data["is_anonymous"])
    await state.update_data(count=data.get("count", 0) + 1)


@router.message(NewPollsStates.waiting_bulk_content, F.text == "/parse")
async def polls_bulk_parse(message: Message, state: FSMContext):
    data = await state.get_data()
    raw = data.get("bulk_raw")
    if not raw:
        await message.answer("Paste your questions first, then send /parse.")
        return
    parsed, errors = parse_bulk(raw)
    if not parsed:
        await message.answer(
            f"Could not parse any questions. Errors: {len(errors)}\n"
            "Check the format and try again."
        )
        return
    await state.update_data(parsed_bulk=[_pq_to_dict(pq) for pq in parsed])
    await state.set_state(NewPollsStates.waiting_bulk_confirm)
    preview = "\n".join(f"{i}. {pq.text[:60]}" for i, pq in enumerate(parsed[:3], 1))
    err_line = f"\n⚠️ {len(errors)} question(s) could not be parsed." if errors else ""
    await message.answer(
        f"Parsed <b>{len(parsed)}</b> question(s):{err_line}\n\n"
        f"<b>Preview:</b>\n{preview}\n\n"
        "Post all polls? Reply <b>yes</b> or <b>no</b>."
    )


@router.message(NewPollsStates.waiting_bulk_content)
async def polls_bulk_capture(message: Message, state: FSMContext):
    await state.update_data(bulk_raw=message.text)
    await message.answer("Received. Send /parse to post the polls.")


@router.message(NewPollsStates.waiting_bulk_confirm, F.text.lower().in_({"yes", "no"}))
async def polls_bulk_confirm(message: Message, state: FSMContext, bot: Bot):
    if message.text.lower() == "no":
        await state.set_state(NewPollsStates.waiting_bulk_content)
        await message.answer("Okay, paste corrected content and send /parse again.")
        return
    data = await state.get_data()
    questions = data.get("parsed_bulk", [])
    is_quiz = data["is_quiz"]
    is_anonymous = data["is_anonymous"]
    await state.clear()
    for q in questions:
        await _send_poll(bot, message.chat.id, _dict_to_pq(q), is_quiz, is_anonymous)
    await message.answer(f"Done! Posted {len(questions)} poll{'s' if len(questions) != 1 else ''}.")


async def _send_poll(
    bot: Bot, chat_id: int, pq: ParsedQuestion, is_quiz: bool, is_anonymous: bool
) -> None:
    if is_quiz:
        await bot.send_poll(
            chat_id=chat_id,
            question=pq.text[:300],
            options=pq.options,
            type="quiz",
            correct_option_id=pq.correct_index,
            is_anonymous=is_anonymous,
            explanation=(pq.reference[:200] if pq.reference else None),
        )
    else:
        await bot.send_poll(
            chat_id=chat_id,
            question=pq.text[:300],
            options=pq.options,
            type="regular",
            is_anonymous=is_anonymous,
        )


def _pq_to_dict(pq: ParsedQuestion) -> dict:
    return {
        "text": pq.text,
        "options": pq.options,
        "correct_index": pq.correct_index,
        "reference": pq.reference,
    }


def _dict_to_pq(d: dict) -> ParsedQuestion:
    return ParsedQuestion(
        text=d["text"],
        options=d["options"],
        correct_index=d["correct_index"],
        reference=d.get("reference"),
    )
