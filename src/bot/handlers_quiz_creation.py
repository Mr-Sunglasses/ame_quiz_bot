from __future__ import annotations

from typing import Any
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot.states import NewQuizStates
from src.config import Settings
from src.db.session import get_session_factory
from src.db.repo import QuizRepo
from src.parser.quiz_parser import parse_single_block, parse_bulk, ParsedQuestion
from .rate_limit import RateLimiter

router = Router()
_rate_limiter = None


@router.message(Command("newquiz"))
async def newquiz(message: Message, state: FSMContext):
    global _rate_limiter
    if _rate_limiter is None:
        settings = Settings.load()
        _rate_limiter = RateLimiter(settings.rate_limit_create_per_hour)
    if not _rate_limiter.allow(message.from_user.id):
        await message.answer("Rate limit: Please try again later.")
        return
    await state.clear()
    await state.set_state(NewQuizStates.waiting_title)
    await message.answer("Quiz title?")


@router.message(NewQuizStates.waiting_title)
async def title_received(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(NewQuizStates.waiting_description)
    await message.answer("Quiz description (optional)? Send /skip to leave empty.")


@router.message(NewQuizStates.waiting_description, F.text == "/skip")
async def description_skipped(message: Message, state: FSMContext):
    await state.update_data(description=None)
    await _ask_mode(message, state)


@router.message(NewQuizStates.waiting_description)
async def description_received(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await _ask_mode(message, state)


async def _ask_mode(message: Message, state: FSMContext):
    await state.set_state(NewQuizStates.waiting_mode)
    await message.answer(
        "Send questions one-by-one or paste all at once. Reply `single` or `bulk`."
    )


@router.message(NewQuizStates.waiting_mode, F.text.lower().in_({"single", "bulk"}))
async def mode_selected(message: Message, state: FSMContext):
    mode = message.text.lower()
    await state.update_data(mode=mode, questions=[])
    if mode == "single":
        await state.set_state(NewQuizStates.waiting_single_question)
        await message.answer(
            "Send question text (see formats). Send /done when finished adding questions."
        )
    else:
        await state.set_state(NewQuizStates.waiting_bulk_content)
        await message.answer(
            "Paste all questions in the supported bulk format. Then send /parse."
        )


@router.message(NewQuizStates.waiting_single_question, F.text == "/done")
async def single_done(message: Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("questions"):
        await message.answer(
            "No questions added yet. Please add at least one or cancel."
        )
        return
    await _ask_duration(message, state)


@router.message(NewQuizStates.waiting_single_question)
async def single_add_question(message: Message, state: FSMContext):
    pq, err = parse_single_block(message.text)
    if err:
        await message.answer(f"Could not parse. Error: {err.message}")
        return
    assert pq
    await _store_temp_question(state, pq)
    idx = len((await state.get_data())["questions"]) - 1
    await message.answer(
        f"Added Q{idx+1}: {pq.text}\nOptions: "
        + ", ".join([f"{i+1}) {o}" for i, o in enumerate(pq.options)])
        + f"\nAnswer saved."
    )


async def _store_temp_question(state: FSMContext, pq: ParsedQuestion):
    data = await state.get_data()
    qs = list(data.get("questions", []))
    qs.append(
        {
            "text": pq.text,
            "options": pq.options,
            "correct_index": pq.correct_index,
            "reference": pq.reference,
        }
    )
    await state.update_data(questions=qs)


@router.message(NewQuizStates.waiting_bulk_content, F.text == "/parse")
async def bulk_parse_command(message: Message, state: FSMContext):
    data = await state.get_data()
    raw = data.get("bulk_raw")
    if not raw:
        await message.answer("Please paste the bulk content first, then send /parse.")
        return
    parsed, errors = parse_bulk(raw)
    preview = parsed[:3]
    preview_lines = []
    for i, pq in enumerate(preview, 1):
        preview_lines.append(f"{i}. {pq.text} \n - Ans saved")
    await state.update_data(
        parsed_bulk=[
            {
                "text": p.text,
                "options": p.options,
                "correct_index": p.correct_index,
                "reference": p.reference,
            }
            for p in parsed
        ]
    )
    await state.set_state(NewQuizStates.waiting_bulk_confirm)
    err_line = f"Errors: {len(errors)}" if errors else ""
    await message.answer(
        "\n".join(
            ["Preview:"]
            + preview_lines
            + [f"Total parsed: {len(parsed)} {err_line}", "Proceed? (yes/no)"]
        )
    )


@router.message(NewQuizStates.waiting_bulk_content)
async def bulk_capture(message: Message, state: FSMContext):
    await state.update_data(bulk_raw=message.text)
    await message.answer("Received. Send /parse to parse the content.")


@router.message(NewQuizStates.waiting_bulk_confirm, F.text.lower().in_({"yes", "no"}))
async def bulk_confirm(message: Message, state: FSMContext):
    if message.text.lower() == "no":
        await state.set_state(NewQuizStates.waiting_bulk_content)
        await message.answer("Okay, paste corrected content and send /parse again.")
        return
    data = await state.get_data()
    await state.update_data(questions=data.get("parsed_bulk", []))
    await _ask_duration(message, state)


async def _ask_duration(message: Message, state: FSMContext):
    await state.set_state(NewQuizStates.waiting_duration)
    await message.answer("Set per-question time in seconds. Send 0 for unlimited.")


@router.message(NewQuizStates.waiting_duration)
async def duration_received(message: Message, state: FSMContext):
    t = message.text.strip().lower()
    seconds = 0
    if t in {"0", "unlimited", "none"}:
        seconds = 0
    else:
        try:
            seconds = max(0, int(t))
        except ValueError:
            await message.answer("Please send a number of seconds, or 0/unlimited.")
            return
    await state.update_data(
        duration_minutes=seconds
    )  # reusing field for per-question seconds
    await state.set_state(NewQuizStates.waiting_visibility)
    await message.answer(
        "Shall this quiz be public or private? Send `public` or `private`."
    )


@router.message(
    NewQuizStates.waiting_visibility, F.text.lower().in_({"public", "private"})
)
async def visibility_received(message: Message, state: FSMContext):
    await state.update_data(public_flag=(message.text.lower() == "public"))
    await state.set_state(NewQuizStates.waiting_confirm)
    data = await state.get_data()
    title = data.get("title")
    desc = data.get("description") or ""
    count = len(data.get("questions", []))
    secs = data.get("duration_minutes")
    await message.answer(
        f"Confirm create quiz? (yes/no)\nTitle: {title}\nDescription: {desc}\nQuestions: {count}\nPer-question time: {secs}s"
    )


@router.message(NewQuizStates.waiting_confirm, F.text.lower().in_({"yes", "no"}))
async def confirm_create(message: Message, state: FSMContext):
    if message.text.lower() == "no":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=ReplyKeyboardRemove())
        return
    data = await state.get_data()
    settings = Settings.load()
    session_factory = get_session_factory()
    async with session_factory() as session:
        repo = QuizRepo(session)
        quiz = await repo.create_quiz(
            creator_id=message.from_user.id,
            title=data["title"],
            description=data.get("description"),
            duration_minutes=data.get("duration_minutes", 0),
            public_flag=data.get("public_flag", True),
        )
        await repo.add_questions(quiz.id, data.get("questions", []))
        await session.commit()
        link = f"https://t.me/{settings.bot_username}?start=quiz_{quiz.id}"
        link_group = f"https://t.me/{settings.bot_username}?startgroup=quiz_{quiz.id}"
        kb = InlineKeyboardBuilder()
        kb.button(text="Share link", url=link)
        kb.button(text="Start quiz", url=link)
        kb.button(text="Start in group", url=link_group)
        await message.answer(
            f"Quiz created!\nTitle: {quiz.title}\nQuestions: {len(data.get('questions', []))}\nPer-question: {data.get('duration_minutes')}s\nLink: {link}",
            reply_markup=kb.as_markup(),
        )
    await state.clear()
