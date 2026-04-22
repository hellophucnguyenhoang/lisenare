from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.services.question_service import process_questions
from ..database import get_session
from ..services.topic_service import  build_learning_tree
from ..services.question_service import get_question_by_exercise_id
router = APIRouter(prefix="/grammar", tags=["Grammar"])

@router.get("/topics")
def get_topics(session: Session = Depends(get_session)):
    # trả về list topics kèm lessons và exercises lồng nhau
    return build_learning_tree(session)

@router.get("/questions/{exercise_id}")
def get_questions(exercise_id: int, session: Session = Depends(get_session)):
    questions = []
    for question in get_question_by_exercise_id(session, exercise_id):
        questions.append(process_questions(question))
    return questions