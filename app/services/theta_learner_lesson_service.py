import math
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.database import (
    Exercise,
    ExerciseType,
    LearnerExercise,
    Lesson,
    ThetaLearnerLesson,
    Topic
)
from app.services.history_answer_question_service import (
    compare_strings
)

def get_theta_by_leaner_and_lesson(session: Session, learner_id, lesson_id):
    statement = select(ThetaLearnerLesson.theta).where(
        ThetaLearnerLesson.learner_id == learner_id
        and ThetaLearnerLesson.lesson_id == lesson_id
    )
    return session.exec(statement).first()

def get_theta_info_by_leaner_and_lesson(session: Session, learner_id):
    statement = (
        select(
            ThetaLearnerLesson.theta.label("theta_lesson"),
            Lesson.name.label("lesson_name"),
            Topic.name.label("topic_name"),
            Lesson.description.label("lesson_description"),
            Topic.description.label("topic_description"),
        )
        .join(Lesson, ThetaLearnerLesson.lesson_id == Lesson.id)
        .join(Topic, Lesson.topic_id == Topic.id)
        .where(ThetaLearnerLesson.learner_id == learner_id)
    )
    return session.exec(statement).all()

def get_theta_average_by_leaner(session: Session, learner_id):
    statement = select(ThetaLearnerLesson.theta).where(
        ThetaLearnerLesson.learner_id == learner_id
    )
    thetas = session.exec(statement).all()
    if not thetas:
        return 0.0
    return sum(thetas) / len(thetas)

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
    theta = max(-3.0, min(3.0, theta))
    return 1 / (1 + math.exp(-a * (theta - b)))

def get_or_insert_theta(session: Session, learner_id: int, lesson_id: int) -> float:
    """Lấy theta của learner cho lesson, nếu chưa có thì insert theta=-3 và trả về -3."""
    existing = session.exec(
        select(ThetaLearnerLesson)
        .where(ThetaLearnerLesson.lesson_id == lesson_id)
        .where(ThetaLearnerLesson.learner_id == learner_id)
    ).first()
    if existing:
        return existing.theta
    else:
        new_record = ThetaLearnerLesson(
            lesson_id=lesson_id, learner_id=learner_id, theta=-3
        )
        session.add(new_record)
        session.commit()
        return -3
    
def update_theta_for_learner(session: Session, learner_id: int, lesson_id: int, questions):
    """Cập nhật theta của learner cho lesson dựa trên các câu hỏi đã trả lời."""
    items = []
    responses = []
    for question, user_answer in questions:
        items.append((1, max(-3, min(3, question.difficulty))))  # a=1, b=difficulty
        responses.append(1 if compare_strings(question.correct_answer, user_answer) else 0)
    if not items or not responses:
        print(f"No items or responses found for learner {learner_id} and lesson {lesson_id}.")
        return
    theta = get_or_insert_theta(session, learner_id, lesson_id)
    new_theta = update_theta(theta=theta, responses=responses, items=items)
    existing = session.exec(
        select(ThetaLearnerLesson)
        .where(ThetaLearnerLesson.lesson_id == lesson_id)
        .where(ThetaLearnerLesson.learner_id == learner_id)
    ).first()
    if existing:
        existing.theta = new_theta
    else:
        session.add(
            ThetaLearnerLesson(
                lesson_id=lesson_id, learner_id=learner_id, theta=new_theta
            )
        )
    session.commit()

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

def mark_lesson_completed_if_done(
    session: Session, learner_id: int, lesson_id: int
) -> bool:
    """Đánh dấu ThetaLearnerLesson.is_completed=True nếu mọi PRACTICE exercise
    của lesson đều có ít nhất 1 LearnerExercise.is_completed=True của learner.

    Trả về True nếu lesson được mark completed (hoặc đã completed trước đó).
    """
    practice_exercise_ids = session.exec(
        select(Exercise.id)
        .where(Exercise.lesson_id == lesson_id)
        .where(Exercise.exercise_type == ExerciseType.PRACTICE)
    ).all()
    if not practice_exercise_ids:
        return False

    completed_exercise_ids = session.exec(
        select(LearnerExercise.exercise_id)
        .where(LearnerExercise.learner_id == learner_id)
        .where(LearnerExercise.exercise_id.in_(practice_exercise_ids))
        .where(LearnerExercise.is_completed.is_(True))
        .distinct()
    ).all()

    if set(completed_exercise_ids) != set(practice_exercise_ids):
        return False

    record = session.exec(
        select(ThetaLearnerLesson)
        .where(ThetaLearnerLesson.learner_id == learner_id)
        .where(ThetaLearnerLesson.lesson_id == lesson_id)
    ).first()

    try:
        if record is None:
            record = ThetaLearnerLesson(
                learner_id=learner_id,
                lesson_id=lesson_id,
                theta=0,
                is_completed=True,
                completed_at=datetime.now(timezone.utc),
            )
            session.add(record)
        elif not record.is_completed:
            record.is_completed = True
            record.completed_at = datetime.now(timezone.utc)
        session.commit()
    except Exception as e:
        session.rollback()
        print(
            f"Mark lesson completed thất bại "
            f"(learner={learner_id}, lesson={lesson_id}): {e}"
        )
        return False

    return True
