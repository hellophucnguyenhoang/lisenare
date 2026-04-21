from ..database import Lesson
from sqlmodel import Session, select

def get_all_lesson_by_topic_id(session: Session, topic_id: int):
    statement = select(Lesson).where(Lesson.topic_id == topic_id)
    results = session.exec(statement)
    return results.all()

def get_lesson_by_id(session: Session, lesson_id: int):
    statement = select(Lesson).where(Lesson.id == lesson_id)
    result = session.exec(statement).first()
    return result

def get_all_lesson(session: Session):
    statement = select(Lesson)
    results = session.exec(statement)
    return results.all()