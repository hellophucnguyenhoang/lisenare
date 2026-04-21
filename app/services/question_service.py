from ..database import Question
from sqlmodel import Session, select

def get_question_by_exercise_id(session: Session, exercise_id: int) -> list[Question]:
    statement = select(Question).where(Question.exercise_id == exercise_id)
    results = session.exec(statement)
    return results.all()

def process_questions(question: Question):
    question_data = {
        "question": question.question,
        "answer": question.answer.split("|"),  # ✅ FIX Ở ĐÂY
        "correct_answer": question.correct_answer,
    }
    return question_data