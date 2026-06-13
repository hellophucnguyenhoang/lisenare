"""Cập nhật difficulty (b) của Question dựa trên lịch sử trả lời của tất cả user.

Cơ chế đối ngẫu với `update_theta` trong theta_learner_lesson_service:
- Theta update: cố định b của các câu hỏi, ước lượng theta của learner.
- Difficulty update: cố định theta của các learner, ước lượng b của câu hỏi.

Cả hai cùng dùng IRT 1PL: P = 1/(1+exp(-(theta - b))) và Newton-Raphson MLE.
"""

import logging
import math
from datetime import datetime, timezone

from sqlalchemy import func
from sqlmodel import Session, select

from app.database import (
    Exercise,
    HistoryAnswerQuestion,
    Question,
    ThetaLearnerLesson,
)
from app.services.history_answer_question_service import compare_strings

logger = logging.getLogger(__name__)

MIN_RESPONSES_DEFAULT = 20
B_MIN, B_MAX = -3.0, 3.0
N_ITER_DEFAULT = 10
EPS_HESSIAN = 1e-9
EPS_DELTA = 1e-6
_SIGMOID_CLIP = 50.0


def _sigmoid(x: float) -> float:
    """Logistic ổn định số học, tránh OverflowError với x lớn."""
    if x >= 0:
        z = math.exp(-min(x, _SIGMOID_CLIP))
        return 1.0 / (1.0 + z)
    z = math.exp(max(x, -_SIGMOID_CLIP))
    return z / (1.0 + z)


def get_questions_to_update(
    session: Session, min_responses: int = MIN_RESPONSES_DEFAULT
) -> list[Question]:
    """Lấy các Question cần recompute difficulty.

    Tiêu chí:
    - Có >= min_responses responses tổng cộng (đủ tin cậy thống kê).
    - Có response mới hơn last_difficulty_update_at (hoặc field này NULL).
    """
    stats_subq = (
        select(
            HistoryAnswerQuestion.question_id.label("qid"),
            func.count(HistoryAnswerQuestion.id).label("cnt"),
            func.max(HistoryAnswerQuestion.timesecond).label("last_ts"),
        )
        .group_by(HistoryAnswerQuestion.question_id)
        .subquery()
    )

    statement = (
        select(Question)
        .join(stats_subq, stats_subq.c.qid == Question.id)
        .where(stats_subq.c.cnt >= min_responses)
        .where(
            (Question.last_difficulty_update_at.is_(None))
            | (stats_subq.c.last_ts > Question.last_difficulty_update_at)
        )
    )
    return list(session.exec(statement).all())


def get_responses_for_question(
    session: Session, question_id: int
) -> list[tuple[float, int]]:
    """Lấy (theta, is_correct) cho mọi response của 1 question.

    JOIN HistoryAnswerQuestion với ThetaLearnerLesson qua learner_id và
    lesson_id (suy ra từ Exercise của Question). Nếu learner chưa có
    ThetaLearnerLesson cho lesson đó thì fallback theta=0.

    Note: dùng theta hiện tại, không phải tại thời điểm trả lời. Đây là
    approximation chấp nhận được vì theta cũng được tính lại từ toàn bộ
    history.
    """
    question = session.get(Question, question_id)
    if question is None:
        return []
    exercise = session.get(Exercise, question.exercise_id)
    if exercise is None or exercise.lesson_id is None:
        return []
    lesson_id = exercise.lesson_id
    correct_answer = question.correct_answer or ""

    statement = (
        select(
            HistoryAnswerQuestion.user_answer,
            ThetaLearnerLesson.theta,
        )
        .join(
            ThetaLearnerLesson,
            (
                ThetaLearnerLesson.learner_id
                == HistoryAnswerQuestion.learner_id
            )
            & (ThetaLearnerLesson.lesson_id == lesson_id),
            isouter=True,
        )
        .where(HistoryAnswerQuestion.question_id == question_id)
    )
    rows = session.exec(statement).all()

    responses: list[tuple[float, int]] = []
    for user_answer, theta in rows:
        if user_answer is None:
            continue
        theta_val = 0.0 if theta is None else float(theta)
        is_correct = (
            1 if compare_strings(correct_answer, user_answer) else 0
        )
        responses.append((theta_val, is_correct))
    return responses


def update_difficulty_b(
    theta_responses: list[tuple[float, int]],
    b_init: float = 0.0,
    n_iter: int = N_ITER_DEFAULT,
) -> float:
    """Newton-Raphson MLE: cố định theta_i, ước lượng b.

    Với a=1 (1PL), log-likelihood của b là:
        L(b) = Σ [u_i * ln P_i + (1-u_i) * ln(1-P_i)]
    Trong đó P_i = 1 / (1 + exp(-(theta_i - b))).

    Đạo hàm:
        dL/db   = Σ (P_i - u_i)
        d²L/db² = -Σ P_i (1 - P_i)

    Newton step: b_new = b - (dL/db) / (d²L/db²).
    Clamp về [B_MIN, B_MAX].
    """
    b = float(b_init)
    for _ in range(n_iter):
        gradient = 0.0
        hessian = 0.0
        for theta, u in theta_responses:
            p = _sigmoid(theta - b)
            gradient += p - u
            hessian -= p * (1.0 - p)

        if abs(hessian) < EPS_HESSIAN:
            break

        delta = gradient / hessian
        b -= delta
        b = max(B_MIN, min(B_MAX, b))

        if abs(delta) < EPS_DELTA:
            break

    return max(B_MIN, min(B_MAX, b))


def recompute_all_due_difficulties(
    session: Session, min_responses: int = MIN_RESPONSES_DEFAULT
) -> dict:
    """Orchestrator: quét questions cần update, tính lại b, ghi DB.

    Commit từng question riêng để 1 lỗi không hỏng cả batch.
    """
    questions = get_questions_to_update(
        session=session, min_responses=min_responses
    )
    stats = {"updated": 0, "skipped": 0, "errors": 0}

    for question in questions:
        try:
            responses = get_responses_for_question(
                session=session, question_id=question.id
            )
            if len(responses) < min_responses:
                stats["skipped"] += 1
                continue

            b_init = (
                question.difficulty
                if question.difficulty is not None
                else 0.0
            )
            new_b = update_difficulty_b(
                theta_responses=responses, b_init=b_init
            )

            question.difficulty = new_b
            question.last_difficulty_update_at = datetime.now(timezone.utc)
            session.add(question)
            session.commit()
            stats["updated"] += 1
        except Exception as e:
            session.rollback()
            stats["errors"] += 1
            logger.exception(
                "Recompute difficulty failed for question_id=%s: %s",
                getattr(question, "id", None),
                e,
            )

    logger.info("Difficulty recompute stats: %s", stats)
    return stats
