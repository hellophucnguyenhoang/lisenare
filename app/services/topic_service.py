from sqlmodel import Session, select

from app.database import Topic

from .exercise_service import get_exercise_by_lesson_id
from .learner_exercise_service import get_completed_exercise_ids
from .lesson_service import get_all_lesson_by_topic_id


def get_all_topic(session: Session):
    statement = select(Topic)
    results = session.exec(statement)
    return results.all()


def get_topic_by_id(session: Session, topic_id: int):
    statement = select(Topic).where(Topic.id == topic_id)
    result = session.exec(statement).first()
    return result


def _percent(completed: int, total: int) -> int:
    return round(completed / total * 100) if total else 0


def build_learning_tree(session, learner_id: int | None = None):
    completed_ids = (
        get_completed_exercise_ids(session, learner_id)
        if learner_id is not None
        else None
    )

    result = []

    for topic in get_all_topic(session):
        topic_data = {"id": topic.id, "name": topic.name, "lessons": []}
        topic_completed = 0
        topic_total = 0

        lessons = get_all_lesson_by_topic_id(session, topic.id)
        for lesson in lessons:
            lesson_data = {
                "id": lesson.id,
                "name": lesson.name,
                "exercises": [],
            }
            lesson_completed = 0

            exercises = get_exercise_by_lesson_id(session, lesson.id)
            for exercise in exercises:
                exercise_data = {"id": exercise.id, "name": exercise.name}
                if completed_ids is not None:
                    done = exercise.id in completed_ids
                    exercise_data["is_completed"] = done
                    if done:
                        lesson_completed += 1
                lesson_data["exercises"].append(exercise_data)

            if completed_ids is not None:
                lesson_total = len(exercises)
                lesson_data["completed_exercises"] = lesson_completed
                lesson_data["total_exercises"] = lesson_total
                lesson_data["progress_percent"] = _percent(
                    lesson_completed, lesson_total
                )
                topic_completed += lesson_completed
                topic_total += lesson_total

            topic_data["lessons"].append(lesson_data)

        if completed_ids is not None:
            topic_data["completed_exercises"] = topic_completed
            topic_data["total_exercises"] = topic_total
            topic_data["progress_percent"] = _percent(
                topic_completed, topic_total
            )

        result.append(topic_data)

    return result
