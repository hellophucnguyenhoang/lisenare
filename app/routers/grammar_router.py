from fastapi import APIRouter, Depends, HTTPException, FastAPI
from sqlmodel import Session

from app.services.question_service import process_questions
from ..database import get_session
from ..services.topic_service import  build_learning_tree
from ..services.lesson_service import get_lesson_by_id
from ..services.exercise_service import get_exercise_by_id, get_exercise_by_lesson_id
from ..services.question_service import get_question_by_exercise_id
from ..services.concept_service import get_root_concept_by_lesson_id
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