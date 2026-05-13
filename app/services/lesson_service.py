from sqlmodel import Session, select

from app.database import Exercise, Lesson, Question


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


def get_lesson_by_question(session: Session, question_id: int):
    statement = (
        select(Lesson)
        .join(Exercise, Lesson.id == Exercise.lesson_id)
        .join(Question, Question.exercise_id == Exercise.id)
        .where(Question.id == question_id)
    )
    lesson = session.exec(statement).first()
    return lesson


def get_lesson_by_exercise(session: Session, exercise_id: int):
    statement = (
        select(Lesson)
        .join(Exercise, Lesson.id == Exercise.lesson_id)
        .where(Exercise.id == exercise_id)
    )
    lesson = session.exec(statement).first()
    return lesson
