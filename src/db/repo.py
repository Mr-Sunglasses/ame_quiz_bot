from __future__ import annotations

from typing import Sequence
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import Quiz, Question, Attempt, Answer, AllowedUser


class QuizRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_quiz(self, creator_id: int, title: str, description: str | None, duration_minutes: int, public_flag: bool) -> Quiz:
        quiz = Quiz(
            creator_id=creator_id,
            title=title,
            description=description,
            duration_minutes=duration_minutes,
            public_flag=public_flag,
        )
        self.session.add(quiz)
        await self.session.flush()
        return quiz

    async def add_questions(self, quiz_id: int, questions: Sequence[dict]) -> list[Question]:
        created: list[Question] = []
        for idx, q in enumerate(questions):
            qrow = Question(
                quiz_id=quiz_id,
                index=idx,
                text=q["text"],
                options=q["options"],
                correct_index=q["correct_index"],
                reference=q.get("reference"),
            )
            self.session.add(qrow)
            created.append(qrow)
        await self.session.flush()
        return created

    async def get_quiz(self, quiz_id: int) -> Quiz | None:
        res = await self.session.execute(select(Quiz).where(Quiz.id == quiz_id))
        return res.scalar_one_or_none()

    async def get_questions(self, quiz_id: int) -> list[Question]:
        res = await self.session.execute(select(Question).where(Question.quiz_id == quiz_id).order_by(Question.index.asc()))
        return list(res.scalars())

    async def list_user_quizzes(self, creator_id: int) -> list[Quiz]:
        res = await self.session.execute(select(Quiz).where(Quiz.creator_id == creator_id).order_by(Quiz.created_at.desc()))
        return list(res.scalars())

    async def add_allowed_users(self, quiz_id: int, user_ids: Sequence[int]) -> None:
        for uid in user_ids:
            self.session.add(AllowedUser(quiz_id=quiz_id, user_id=uid))
        await self.session.flush()

    async def is_user_allowed(self, quiz_id: int, user_id: int) -> bool:
        res = await self.session.execute(
            select(AllowedUser).where(AllowedUser.quiz_id == quiz_id, AllowedUser.user_id == user_id)
        )
        return res.scalar_one_or_none() is not None

    async def delete_quiz_if_owner(self, quiz_id: int, requester_id: int) -> bool:
        quiz = await self.get_quiz(quiz_id)
        if not quiz or quiz.creator_id != requester_id:
            return False
        await self.session.execute(delete(Quiz).where(Quiz.id == quiz_id))
        await self.session.flush()
        return True


class AttemptRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_attempt(self, quiz_id: int, user_id: int) -> Attempt:
        attempt = Attempt(quiz_id=quiz_id, user_id=user_id)
        self.session.add(attempt)
        await self.session.flush()
        return attempt

    async def finish_attempt(self, attempt_id: int, score: int) -> None:
        from sqlalchemy import select
        from src.db.models import Attempt as AttemptModel
        res = await self.session.execute(select(AttemptModel).where(AttemptModel.id == attempt_id))
        att = res.scalar_one()
        att.score = score
        from datetime import datetime
        att.finished_at = datetime.utcnow()
        await self.session.flush()

    async def upsert_answer(self, attempt_id: int, question_id: int, chosen_index: int, is_correct: bool) -> None:
        await self.session.execute(delete(Answer).where(Answer.attempt_id == attempt_id, Answer.question_id == question_id))
        self.session.add(Answer(
            attempt_id=attempt_id,
            question_id=question_id,
            chosen_index=chosen_index,
            is_correct=is_correct,
        ))
        await self.session.flush()

    async def get_answers(self, attempt_id: int) -> list[Answer]:
        res = await self.session.execute(select(Answer).where(Answer.attempt_id == attempt_id))
        return list(res.scalars())
