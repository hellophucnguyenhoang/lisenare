from sqlmodel import Session, select

from app.services.exercise_service import get_exercise_by_lesson_id
from app.services.lesson_service import get_lesson_by_id



def get_lesson_detail(session: Session, lesson_id: int) -> dict:
    if lesson_id is None:
        return {
            "ok": False,
            "tool": "get_lesson_detail",
            "summary": "Thiếu lesson_id",
            "error": "missing lesson_id",
        }

    lesson = get_lesson_by_id(session, lesson_id)
    if lesson is None:
        return {
            "ok": False,
            "tool": "get_lesson_detail",
            "summary": f"Không tìm thấy lesson_id={lesson_id}",
            "error": "lesson not found",
        }

    exercises = get_exercise_by_lesson_id(session, lesson_id)

    return {
        "ok": True,
        "tool": "get_lesson_detail",
        "summary": (
            f"Lesson '{lesson.name}': {len(exercises)} exercises"
        ),
        "data": {
            "lesson_id": lesson.id,
            "lesson_name": lesson.name,
            "lesson_description": lesson.description,
            "topic_id": lesson.topic_id,
            "exercises": [
                {
                    "id": e.id,
                    "name": e.name,
                    "difficulty": e.difficulty,
                }
                for e in exercises
            ],
        },
    }
