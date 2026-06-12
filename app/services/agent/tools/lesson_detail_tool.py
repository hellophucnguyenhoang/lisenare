from sqlmodel import Session, select

from app.database import Concept
from app.services.exercise_service import get_exercise_by_lesson_id
from app.services.lesson_service import get_lesson_by_id


def _get_concepts_by_lesson_id(
    session: Session, lesson_id: int
) -> list[Concept]:
    statement = select(Concept).where(Concept.lesson_id == lesson_id)
    return list(session.exec(statement).all())


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

    concepts = _get_concepts_by_lesson_id(session, lesson_id)
    exercises = get_exercise_by_lesson_id(session, lesson_id)

    return {
        "ok": True,
        "tool": "get_lesson_detail",
        "summary": (
            f"Lesson '{lesson.name}': {len(concepts)} concepts, "
            f"{len(exercises)} exercises"
        ),
        "data": {
            "lesson_id": lesson.id,
            "lesson_name": lesson.name,
            "lesson_description": lesson.description,
            "topic_id": lesson.topic_id,
            "concepts": [
                {
                    "id": c.id,
                    "name": c.name,
                    "type": c.type,
                    "description": c.description,
                }
                for c in concepts
            ],
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
