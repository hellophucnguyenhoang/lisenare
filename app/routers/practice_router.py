import redis
from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import get_session
from app.redis_client import get_redis
from app.schemas.practice import (
    AnswerPracticeRequest,
    AnswerPracticeResponse,
    EndPracticeRequest,
    StartPracticeRequest,
    StartPracticeResponse,
)
from app.services.practice_service import (
    end_practice_session,
    start_practice_session,
    submit_practice_answer,
)

router = APIRouter(prefix="/practice", tags=["Practice"])


@router.post("/start", response_model=StartPracticeResponse)
def start(
    body: StartPracticeRequest,
    session: Session = Depends(get_session),
    r: redis.Redis = Depends(get_redis),
):
    session_id, theta, question = start_practice_session(
        session=session,
        r=r,
        learner_id=body.learner_id,
        topic_ids=body.topic_ids,
    )
    return StartPracticeResponse(
        session_id=session_id, theta=theta, question=question
    )


@router.post("/answer", response_model=AnswerPracticeResponse)
def answer(
    body: AnswerPracticeRequest,
    session: Session = Depends(get_session),
    r: redis.Redis = Depends(get_redis),
):
    result = submit_practice_answer(
        session=session,
        r=r,
        session_id=body.session_id,
        learner_id=body.learner_id,
        question_id=body.question_id,
        user_answer=body.user_answer,
    )
    return AnswerPracticeResponse(**result)


@router.post("/end")
def end(
    body: EndPracticeRequest,
    r: redis.Redis = Depends(get_redis),
):
    return end_practice_session(
        r=r, session_id=body.session_id, learner_id=body.learner_id
    )
