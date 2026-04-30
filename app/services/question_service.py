from sqlmodel import Session, select

from app.database import Question


def get_question_by_exercise_id(
    session: Session, exercise_id: int
) -> list[Question]:
    statement = (
        select(Question)
        .where(Question.exercise_id == exercise_id)
        .order_by(Question.difficulty.desc())
    )
    results = session.exec(statement)
    return results.all()


def process_questions(question: Question):
    question_data = {
        "question": question.question,
        "question_id": question.id,
        "answer": question.answer.split("|"),
        "correct_answer": question.correct_answer,
    }
    return question_data
