import math

from sqlmodel import Session, select

from app.database import ThetaLearnerLesson
from app.services.history_answer_question_service import (
    get_difficulty_and_respone,
)


def get_theta_by_leaner_and_lesson(session: Session, learner_id, lesson_id):
    statement = select(ThetaLearnerLesson.theta).where(
        ThetaLearnerLesson.learner_id == learner_id
        and ThetaLearnerLesson.lesson_id == lesson_id
    )
    return session.exec(statement).first()


def update_theta(theta, items, responses, n_iter=10):
    """
    items     : list of (a, b)
    responses : list of 0/1
    """
    for _ in range(n_iter):
        numerator = 0.0  # Σ a_j(u_j - P_j)
        denominator = 0.0  # Σ a_j² * P_j(1 - P_j)

        for (a, b), u in zip(items, responses):
            prob = computeP(theta, a, b)
            numerator += a * (u - prob)
            denominator += a**2 * prob * (1 - prob)

        if abs(denominator) < 1e-9:
            break

        delta = numerator / denominator
        theta += delta  # ← dấu + theo đúng công thức ảnh

        if abs(delta) < 1e-6:
            break

    # Clamp trong [-4, 4]
    return max(-3.0, min(3.0, theta))


def computeP(theta, a, b):
    return 1 / (1 + math.exp(-a * (theta - b)))


def insert_or_update_theta(session: Session, lesson_id: int, learner_id: int):
    items, responses = get_difficulty_and_respone(
        session=session, learner_id=learner_id, lesson_id=lesson_id
    )
    theta = update_theta(theta=0, responses=responses, items=items)
    existing = session.exec(
        select(ThetaLearnerLesson)
        .where(ThetaLearnerLesson.lesson_id == lesson_id)
        .where(ThetaLearnerLesson.learner_id == learner_id)
    ).first()

    try:
        if existing:
            existing.theta = theta
        else:
            session.add(
                ThetaLearnerLesson(
                    lesson_id=lesson_id, learner_id=learner_id, theta=theta
                )
            )

        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Cập nhật theta thất bại: {e}")


def save_theta_value(
    session: Session, learner_id: int, lesson_id: int, theta: float
) -> None:
    """Lưu thẳng giá trị theta đã tính (dùng cho practice session)."""
    existing = session.exec(
        select(ThetaLearnerLesson)
        .where(ThetaLearnerLesson.lesson_id == lesson_id)
        .where(ThetaLearnerLesson.learner_id == learner_id)
    ).first()
    try:
        if existing:
            existing.theta = theta
        else:
            session.add(
                ThetaLearnerLesson(
                    lesson_id=lesson_id, learner_id=learner_id, theta=theta
                )
            )
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Lưu theta thất bại (learner={learner_id}, lesson={lesson_id}): {e}")


def theta_to_level(theta: float) -> str:
    """Chuyển theta (-3 đến 3) thành level CEFR (A1-C2)"""
    if theta < -2:
        return "A1"
    elif theta < -1:
        return "A2"
    elif theta < 0:
        return "B1"
    elif theta < 1:
        return "B2"
    elif theta < 2:
        return "C1"
    else:
        return "C2"
