from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.schemas import SubmitRequest
from app.database import HistoryAnswerQuestion
from app.database import get_session
from datetime import datetime
from app.services.question_service import (
    get_question_by_exercise_id,
    process_questions,
)
from app.services.topic_service import build_learning_tree
from app.services.history_answer_question_service import insert_list_history_answer_question

router = APIRouter(prefix="/grammar", tags=["Grammars"])


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

@router.post("/submit")
def submit_exercise(data : SubmitRequest, session: Session = Depends(get_session)):
    time = datetime.now()
    records = [
        HistoryAnswerQuestion(
            learner_id=data.user_id,
            question_id=ans.question_id,
            user_answer=ans.user_answer,
            timestamp = time
        )
        for ans in data.answers
    ]
    insert_list_history_answer_question(session, records)
    return {"message": "Nộp bài thành công và đã thêm vào database"}
    