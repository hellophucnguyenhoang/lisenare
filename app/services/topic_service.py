from sqlmodel import Session, select

from ..database import Topic
from .lesson_service import get_all_lesson_by_topic_id
from .exercise_service import get_exercise_by_lesson_id
def get_all_topic(session: Session):
    statement = select(Topic)
    results = session.exec(statement)
    return results.all()

def get_topic_by_id(session: Session, topic_id: int):
    statement = select(Topic).where(Topic.id == topic_id)
    result = session.exec(statement).first()
    return result

def build_learning_tree(session):
    result = []

    for topic in get_all_topic(session):
        topic_data = {
            "id": topic.id,
            "name": topic.name,
            "lessons": []
        }

        lessons = get_all_lesson_by_topic_id(session, topic.id)
        for lesson in lessons:
            lesson_data = {
                "id": lesson.id,
                "name": lesson.name,
                "exercises": []
            }

            exercises = get_exercise_by_lesson_id(session, lesson.id)
            for exercise in exercises:
                lesson_data["exercises"].append({
                    "id": exercise.id,
                    "name": exercise.name
                })

            topic_data["lessons"].append(lesson_data)

        result.append(topic_data)

    return result