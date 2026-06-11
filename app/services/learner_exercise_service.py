from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.database import (
    Exercise,
    HistoryAnswerQuestion,
    LearnerExercise,
)
from app.services.theta_learner_lesson_service import (
    mark_lesson_completed_if_done,
)

COMPLETION_THRESHOLD = 0.9


def start_attempt(
    session: Session, learner_id: int, exercise_id: int
) -> LearnerExercise:
    attempt = LearnerExercise(
        learner_id=learner_id,
        exercise_id=exercise_id,
        started_at=datetime.now(timezone.utc),
    )
    session.add(attempt)
    session.flush()
    return attempt


def record_answer(
    session: Session,
    attempt_id: int,
    learner_id: int,
    question_id: int,
    user_answer: str | None,
) -> HistoryAnswerQuestion:
    history = HistoryAnswerQuestion(
        learner_id=learner_id,
        question_id=question_id,
        user_answer=user_answer,
        timesecond=datetime.now(timezone.utc),
        learner_exercise_id=attempt_id,
    )
    session.add(history)
    return history


def finish_attempt(
    session: Session,
    attempt: LearnerExercise,
    num_correct: int,
    num_incorrect: int,
) -> LearnerExercise:
    attempt.num_correct_questions = num_correct
    attempt.num_incorrect_questions = num_incorrect
    total = num_correct + num_incorrect
    attempt.is_completed = (
        total > 0 and (num_correct / total) > COMPLETION_THRESHOLD
    )
    attempt.ended_at = datetime.now(timezone.utc)

    try:
        session.commit()
        session.refresh(attempt)
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Không lưu được attempt: {e}",
        )

    if attempt.is_completed:
        lesson_id = session.exec(
            select(Exercise.lesson_id).where(Exercise.id == attempt.exercise_id)
        ).first()
        if lesson_id is not None:
            mark_lesson_completed_if_done(
                session, learner_id=attempt.learner_id, lesson_id=lesson_id
            )

    return attempt


def get_attempt_by_id(
    session: Session, attempt_id: int
) -> LearnerExercise | None:
    return session.get(LearnerExercise, attempt_id)


def get_attempts_by_learner_and_exercise(
    session: Session, learner_id: int, exercise_id: int
) -> list[LearnerExercise]:
    statement = (
        select(LearnerExercise)
        .where(LearnerExercise.learner_id == learner_id)
        .where(LearnerExercise.exercise_id == exercise_id)
        .order_by(LearnerExercise.started_at.desc())
    )
    return session.exec(statement).all()
