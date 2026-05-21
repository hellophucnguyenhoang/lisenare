import random
import uuid
from datetime import datetime, timezone

import redis
from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.config import settings
from app.database import (
    Exercise,
    ExerciseType,
    HistoryAnswerQuestion,
    Lesson,
    Question,
    ThetaLearnerLesson,
)
from app.schemas.practice import PracticeQuestionResponse
from app.services.history_answer_question_service import (
    compare_strings,
    insert_history_answer_question,
)
from app.services.theta_learner_lesson_service import update_theta


# ---------------------------------------------------------------------------
# Redis key helpers
# ---------------------------------------------------------------------------

def _pool_key(session_id: str) -> str:
    return f"practice:session:{session_id}:pool"


def _state_key(session_id: str) -> str:
    return f"practice:session:{session_id}:state"


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def _load_state(r: redis.Redis, session_id: str) -> dict:
    state = r.hgetall(_state_key(session_id))
    if not state:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Practice session expired or not found",
        )
    return state


def _assert_learner(state: dict, learner_id: int) -> None:
    if int(state.get("learner_id", -1)) != learner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="learner_id does not match this practice session",
        )


# ---------------------------------------------------------------------------
# Question selection
# ---------------------------------------------------------------------------

# Difficulty windows around theta (corresponds to P(correct) in [0.4, 0.6]
# for the simple IRT model 1 / (1 + exp(-(theta - b))) ).
_WINDOWS = [0.405, 0.8, 1.2, 2.0]


def select_next_question_id(
    r: redis.Redis, session_id: str, theta: float
) -> int | None:
    """Pick a question_id from the Redis pool whose difficulty is near theta.

    Expands the window progressively. Falls back to the closest remaining
    question when no candidates lie in any window.
    """
    key = _pool_key(session_id)
    for half in _WINDOWS:
        members = r.zrangebyscore(key, theta - half, theta + half)
        if members:
            return int(random.choice(members))

    # No question in any window — pick the closest by absolute distance.
    all_members = r.zrange(key, 0, -1, withscores=True)
    if not all_members:
        return None
    closest = min(all_members, key=lambda m: abs(m[1] - theta))
    return int(closest[0])


# ---------------------------------------------------------------------------
# Question payload
# ---------------------------------------------------------------------------

def get_question_public_payload(
    session: Session, question_id: int
) -> PracticeQuestionResponse:
    question = session.exec(
        select(Question).where(Question.id == question_id)
    ).first()
    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question {question_id} not found",
        )
    return PracticeQuestionResponse(
        id=question.id,
        question=question.question,
        content=question.content,
        answer=question.answer,
        type=question.type,
        difficulty=question.difficulty or 0.0,
    )


# ---------------------------------------------------------------------------
# Theta initialization
# ---------------------------------------------------------------------------

def _initial_theta(
    session: Session, learner_id: int, topic_ids: list[int]
) -> float:
    """Average existing per-lesson theta for lessons in the chosen topics.

    Falls back to 0.0 if the learner has no theta record yet.
    """
    statement = (
        select(ThetaLearnerLesson.theta)
        .join(Lesson, ThetaLearnerLesson.lesson_id == Lesson.id)
        .where(ThetaLearnerLesson.learner_id == learner_id)
        .where(Lesson.topic_id.in_(topic_ids))
    )
    values = [v for v in session.exec(statement).all() if v is not None]
    if not values:
        return 0.0
    return sum(values) / len(values)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_practice_session(
    session: Session,
    r: redis.Redis,
    learner_id: int,
    topic_ids: list[int],
) -> tuple[str, float, PracticeQuestionResponse]:
    if not topic_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="topic_ids must not be empty",
        )

    # Single join to load (question_id, difficulty) for the entire pool.
    statement = (
        select(Question.id, Question.difficulty)
        .join(Exercise, Question.exercise_id == Exercise.id)
        .join(Lesson, Exercise.lesson_id == Lesson.id)
        .where(Lesson.topic_id.in_(topic_ids))
        .where(Exercise.exercise_type == ExerciseType.REVIEW)
    )
    rows = session.exec(statement).all()
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No REVIEW questions found for the selected topics",
        )

    session_id = uuid.uuid4().hex
    pool_key = _pool_key(session_id)
    state_key = _state_key(session_id)

    # Populate sorted set with score=difficulty.
    mapping = {str(qid): float(diff or 0.0) for qid, diff in rows}
    r.zadd(pool_key, mapping)

    theta = _initial_theta(session, learner_id, topic_ids)

    first_qid = select_next_question_id(r, session_id, theta)
    if first_qid is None:
        # Shouldn't happen because rows is non-empty; cleanup just in case.
        r.delete(pool_key)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not pick an initial question",
        )

    state = {
        "learner_id": str(learner_id),
        "theta": str(theta),
        "current_question_id": str(first_qid),
        "topic_ids": ",".join(str(t) for t in topic_ids),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    r.hset(state_key, mapping=state)
    r.expire(pool_key, settings.practice_session_ttl)
    r.expire(state_key, settings.practice_session_ttl)

    question = get_question_public_payload(session, first_qid)
    return session_id, theta, question


def submit_practice_answer(
    session: Session,
    r: redis.Redis,
    session_id: str,
    learner_id: int,
    question_id: int,
    user_answer: str,
) -> dict:
    state = _load_state(r, session_id)
    _assert_learner(state, learner_id)

    current_qid = int(state.get("current_question_id", -1))
    if current_qid != question_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="question_id is not the current question of this session",
        )

    question = session.exec(
        select(Question).where(Question.id == question_id)
    ).first()
    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question {question_id} not found",
        )

    is_correct = compare_strings(
        question.correct_answer or "", user_answer or ""
    )

    insert_history_answer_question(
        session,
        HistoryAnswerQuestion(
            learner_id=learner_id,
            question_id=question_id,
            user_answer=user_answer,
            timesecond=datetime.now(timezone.utc),
        ),
    )

    # Update theta using current state theta + this single response.
    theta = float(state.get("theta", 0.0))
    difficulty = float(question.difficulty or 0.0)
    new_theta = update_theta(
        theta,
        items=[(1, difficulty)],
        responses=[1 if is_correct else 0],
    )

    # Remove the answered question from the pool.
    r.zrem(_pool_key(session_id), str(question_id))

    next_qid = select_next_question_id(r, session_id, new_theta)
    practice_completed = next_qid is None
    next_question: PracticeQuestionResponse | None = None

    state_key = _state_key(session_id)
    if practice_completed:
        # Pool empty — keep state for a moment, but clear current_question_id.
        r.hset(state_key, mapping={"theta": str(new_theta)})
        r.hdel(state_key, "current_question_id")
    else:
        next_question = get_question_public_payload(session, next_qid)
        r.hset(
            state_key,
            mapping={
                "theta": str(new_theta),
                "current_question_id": str(next_qid),
            },
        )
    r.expire(state_key, settings.practice_session_ttl)
    if not practice_completed:
        r.expire(_pool_key(session_id), settings.practice_session_ttl)

    return {
        "is_correct": is_correct,
        "correct_answer": question.correct_answer,
        "theta": new_theta,
        "practice_completed": practice_completed,
        "next_question": next_question,
    }


def end_practice_session(
    r: redis.Redis, session_id: str, learner_id: int
) -> dict:
    state = _load_state(r, session_id)
    _assert_learner(state, learner_id)
    r.delete(_pool_key(session_id), _state_key(session_id))
    return {"message": "Practice session ended"}
