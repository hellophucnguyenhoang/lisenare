from sqlmodel import Session, select

from app.database import Exercise
from app.database.models import ExerciseType

def get_exercise_by_id(session: Session, exercise_id: int) -> Exercise:
    statement = select(Exercise).where(Exercise.id == exercise_id)
    result = session.exec(statement).first()
    return result


def get_exercise_by_lesson_id(
    session: Session, lesson_id: int
) -> list[Exercise]:
    statement = select(Exercise).where(
        Exercise.lesson_id == lesson_id,
        Exercise.exercise_type == ExerciseType.PRACTICE,
    )
    results = session.exec(statement)
    return results.all()
