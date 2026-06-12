from sqlmodel import Session, func, select

from app.database import (
    Exercise,
    ExerciseType,
    Lesson,
    Question,
    ThetaLearnerLesson,
    Topic,
)
from app.services.theta_learner_lesson_service import (
    get_theta_average_by_leaner,
    theta_to_level,
)


def recommend_questions(
    session: Session,
    learner_id: int,
    topic_id: int | None = None,
    limit: int = 5,
) -> dict:
    """Gợi ý câu hỏi luyện tập có độ khó gần theta của learner.

    - Nếu có `topic_id` thì chỉ lấy question thuộc topic đó.
    - Lấy lesson theta của learner (nếu có) để chọn câu phù hợp;
      mặc định dùng theta trung bình.
    """
    limit = max(1, min(int(limit or 5), 10))

    try:
        avg_theta = get_theta_average_by_leaner(session, learner_id) or 0.0
    except Exception:
        avg_theta = 0.0

    statement = (
        select(
            Question.id,
            Question.question,
            Question.answer,
            Question.difficulty,
            Lesson.id.label("lesson_id"),
            Lesson.name.label("lesson_name"),
            Topic.name.label("topic_name"),
            ThetaLearnerLesson.theta.label("lesson_theta"),
        )
        .join(Exercise, Question.exercise_id == Exercise.id)
        .join(Lesson, Exercise.lesson_id == Lesson.id)
        .join(Topic, Lesson.topic_id == Topic.id)
        .join(
            ThetaLearnerLesson,
            (ThetaLearnerLesson.lesson_id == Lesson.id)
            & (ThetaLearnerLesson.learner_id == learner_id),
            isouter=True,
        )
        .where(Exercise.exercise_type == ExerciseType.PRACTICE)
    )

    if topic_id is not None:
        statement = statement.where(Topic.id == topic_id)

    statement = statement.order_by(
        func.abs(
            func.coalesce(Question.difficulty, 0.0)
            - func.coalesce(ThetaLearnerLesson.theta, avg_theta)
        )
    ).limit(limit)

    rows = session.exec(statement).all()
    items = []
    for r in rows:
        mapping = getattr(r, "_mapping", None)
        get = (
            (lambda k, idx: mapping[k])
            if mapping is not None
            else (lambda k, idx, row=r: getattr(row, k, row[idx]))
        )
        items.append(
            {
                "question_id": get("id", 0),
                "question": get("question", 1),
                "answer": get("answer", 2),
                "difficulty": get("difficulty", 3),
                "lesson_id": get("lesson_id", 4),
                "lesson_name": get("lesson_name", 5),
                "topic_name": get("topic_name", 6),
                "lesson_theta": get("lesson_theta", 7),
            }
        )

    return {
        "ok": True,
        "tool": "recommend_questions",
        "summary": (
            f"Đã chọn {len(items)} câu phù hợp "
            f"(theta TB {avg_theta:.2f}, level {theta_to_level(avg_theta)})"
        ),
        "data": {
            "learner_theta": avg_theta,
            "level": theta_to_level(avg_theta),
            "topic_id": topic_id,
            "questions": items,
        },
    }
