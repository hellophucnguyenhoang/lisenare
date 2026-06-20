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
from app.services.theta_learner_lesson_service import (
    save_theta_value,
    update_theta,
)

# ---------------------------------------------------------------------------
# Redis key helpers
# ---------------------------------------------------------------------------


def _pool_key(session_id: str) -> str:
    return f"practice:session:{session_id}:pool"


def _state_key(session_id: str) -> str:
    return f"practice:session:{session_id}:state"


def _lesson_thetas_key(session_id: str) -> str:
    """Hash: lesson_id -> theta (float)"""
    return f"practice:session:{session_id}:lesson_thetas"


def _question_lesson_key(session_id: str) -> str:
    """Hash: question_id -> lesson_id"""
    return f"practice:session:{session_id}:question_lesson"


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
# Lesson theta helpers
# ---------------------------------------------------------------------------


def _get_lesson_theta(
    r: redis.Redis, session_id: str, question_id: int
) -> tuple[str | None, float]:
    """Trả về (lesson_id_str, theta) của lesson chứa question_id. None nếu không tìm thấy."""
    lid_raw = r.hget(_question_lesson_key(session_id), str(question_id))
    if lid_raw is None:
        return None, 0.0
    lid_str = lid_raw.decode() if isinstance(lid_raw, bytes) else str(lid_raw)
    raw = r.hget(_lesson_thetas_key(session_id), lid_str)
    lesson_theta = float(raw) if raw is not None else 0.0
    return lid_str, lesson_theta


def _flush_lesson_thetas(
    r: redis.Redis, session_id: str, session: Session, learner_id: int
) -> None:
    """Đọc tất cả lesson theta từ Redis và lưu vào database."""
    lesson_thetas = r.hgetall(_lesson_thetas_key(session_id))
    for lid_bytes, theta_bytes in lesson_thetas.items():
        lid = int(
            lid_bytes.decode() if isinstance(lid_bytes, bytes) else lid_bytes
        )
        theta = float(
            theta_bytes.decode()
            if isinstance(theta_bytes, bytes)
            else theta_bytes
        )
        save_theta_value(
            session, learner_id=learner_id, lesson_id=lid, theta=theta
        )


# ---------------------------------------------------------------------------
# Question selection
# ---------------------------------------------------------------------------

# Difficulty windows around theta (corresponds to P(correct) in [0.4, 0.6]
# for the simple IRT model 1 / (1 + exp(-(theta - b))) ).
_WINDOWS = [0.405, 0.8, 1.2, 2.0]


def _pick_by_lowest_lesson_theta(
    r: redis.Redis, session_id: str, candidates: list
) -> int:
    """Trong danh sách candidates, chọn câu hỏi có lesson theta thấp nhất."""
    ql_key = _question_lesson_key(session_id)
    lt_key = _lesson_thetas_key(session_id)

    best_qid: int | None = None
    best_lesson_theta = float("inf")

    for member in candidates:
        qid = int(member)
        lid_raw = r.hget(ql_key, str(qid))
        if lid_raw is None:
            lesson_theta = 0.0
        else:
            lid_str = (
                lid_raw.decode()
                if isinstance(lid_raw, bytes)
                else str(lid_raw)
            )
            raw = r.hget(lt_key, lid_str)
            lesson_theta = float(raw) if raw is not None else 0.0

        if lesson_theta < best_lesson_theta:
            best_lesson_theta = lesson_theta
            best_qid = qid

    return best_qid if best_qid is not None else int(candidates[0])


def select_next_question_id(
    r: redis.Redis, session_id: str, theta: float
) -> int | None:
    """Pick a question_id from the Redis pool whose difficulty is near theta.

    Expands the window progressively. Khi có nhiều ứng viên cùng window,
    chọn câu thuộc lesson có theta thấp nhất thay vì random.
    Falls back to the closest remaining question when no candidates lie in any window.
    """
    key = _pool_key(session_id)
    for half in _WINDOWS:
        members = r.zrangebyscore(key, theta - half, theta + half)
        if members:
            return _pick_by_lowest_lesson_theta(r, session_id, members)

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

    # Load (question_id, difficulty, lesson_id) cho toàn bộ pool.
    statement = (
        select(Question.id, Question.difficulty, Lesson.id)
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

    # Tổng hợp lesson_ids duy nhất từ pool.
    lesson_ids = list({row[2] for row in rows})

    # Lấy theta hiện tại từ DB cho từng lesson; nếu chưa có thì 0.0.
    theta_records = session.exec(
        select(ThetaLearnerLesson)
        .where(ThetaLearnerLesson.learner_id == learner_id)
        .where(ThetaLearnerLesson.lesson_id.in_(lesson_ids))
    ).all()
    lesson_theta_map: dict[int, float] = {
        rec.lesson_id: (rec.theta or 0.0) for rec in theta_records
    }
    for lid in lesson_ids:
        if lid not in lesson_theta_map:
            lesson_theta_map[lid] = 0.0

    session_id = uuid.uuid4().hex

    # Sorted set: score = difficulty
    pool_mapping = {str(qid): float(diff or 0.0) for qid, diff, _ in rows}
    r.zadd(_pool_key(session_id), pool_mapping)

    # Hash: question_id -> lesson_id
    r.hset(
        _question_lesson_key(session_id),
        mapping={str(qid): str(lid) for qid, _, lid in rows},
    )

    # Hash: lesson_id -> theta
    r.hset(
        _lesson_thetas_key(session_id),
        mapping={str(lid): str(th) for lid, th in lesson_theta_map.items()},
    )

    # Session theta = trung bình theta các lesson (làm điểm khởi đầu cho IRT window)
    theta = sum(lesson_theta_map.values()) / len(lesson_theta_map)

    first_qid = select_next_question_id(r, session_id, theta)
    if first_qid is None:
        r.delete(
            _pool_key(session_id),
            _question_lesson_key(session_id),
            _lesson_thetas_key(session_id),
        )
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
    ttl = settings.practice_session_ttl
    r.hset(_state_key(session_id), mapping=state)
    r.expire(_pool_key(session_id), ttl)
    r.expire(_state_key(session_id), ttl)
    r.expire(_question_lesson_key(session_id), ttl)
    r.expire(_lesson_thetas_key(session_id), ttl)

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

    # Cập nhật session theta (dùng cho IRT window lần sau).
    theta = float(state.get("theta", 0.0))
    difficulty = float(question.difficulty or 0.0)
    response = 1 if is_correct else 0
    new_theta = update_theta(
        theta, items=[(1, difficulty)], responses=[response]
    )

    # Cập nhật theta của lesson chứa câu vừa trả lời trong Redis.
    lid_str, old_lesson_theta = _get_lesson_theta(r, session_id, question_id)
    if lid_str is not None:
        new_lesson_theta = update_theta(
            old_lesson_theta, items=[(1, difficulty)], responses=[response]
        )
        r.hset(_lesson_thetas_key(session_id), lid_str, str(new_lesson_theta))

    # Xóa câu vừa làm khỏi pool.
    r.zrem(_pool_key(session_id), str(question_id))

    next_qid = select_next_question_id(r, session_id, new_theta)
    practice_completed = next_qid is None
    next_question: PracticeQuestionResponse | None = None

    state_key = _state_key(session_id)
    ttl = settings.practice_session_ttl

    if practice_completed:
        # Pool rỗng — lưu lesson thetas vào DB ngay lập tức.
        _flush_lesson_thetas(r, session_id, session, learner_id)
        r.delete(
            _lesson_thetas_key(session_id), _question_lesson_key(session_id)
        )
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
        r.expire(_pool_key(session_id), ttl)
        r.expire(_question_lesson_key(session_id), ttl)
        r.expire(_lesson_thetas_key(session_id), ttl)

    r.expire(state_key, ttl)

    return {
        "is_correct": is_correct,
        "correct_answer": question.correct_answer,
        "theta": new_theta,
        "practice_completed": practice_completed,
        "next_question": next_question,
    }


def end_practice_session(
    r: redis.Redis, session_id: str, learner_id: int, session: Session
) -> dict:
    state = _load_state(r, session_id)
    _assert_learner(state, learner_id)
    # Lưu lesson thetas còn lại vào DB trước khi xóa.
    _flush_lesson_thetas(r, session_id, session, learner_id)
    r.delete(
        _pool_key(session_id),
        _state_key(session_id),
        _lesson_thetas_key(session_id),
        _question_lesson_key(session_id),
    )
    return {"message": "Practice session ended"}
