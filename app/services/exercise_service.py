from ..database import Exercise
from sqlmodel import Session, select

def get_exercise_by_id(session: Session, exercise_id: int) -> Exercise:
    statement = select(Exercise).where(Exercise.id == exercise_id)
    result = session.exec(statement).first()
    return result

def get_exercise_by_lesson_id(session: Session, lesson_id: int) -> list[Exercise]:
    statement = select(Exercise).where(Exercise.lesson_id == lesson_id)
    results = session.exec(statement)
    return results.all()