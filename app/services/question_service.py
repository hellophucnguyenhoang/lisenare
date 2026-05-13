from sqlmodel import Session, select

from app.database import Question
from app.schemas.grammar import QuestionContext
from app.services.history_answer_question_service import compare_strings


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


def get_question_by_id(session: Session, id: int) -> Question:
    statement = select(Question).where(Question.id == id)
    question = session.exec(statement).first()
    return question


def evaluate_questions(
    questions: list[QuestionContext], session: Session
) -> tuple[list, list]:
    items = []
    responses = []

    for q in questions:
        question = get_question_by_id(session, q.question_id)
        is_correct = compare_strings(question.answer, q.user_answer)
        items.append([1, question.difficulty])
        responses.append(1 if is_correct else 0)

    return items, responses
