# app/api/study_sessions.py
from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.database import get_session
from app.schemas import EventUpdate, Submition
from app.services import study_sessions as study_session_services

router = APIRouter(prefix="/study_sessions", tags=["StudySessions"])


@router.patch("/{id}/event")
def update_event_api(id: int, even_update: EventUpdate, session: Session = Depends(get_session)):
    return study_session_services.update_event(session, id, event_type=even_update.event_type)

@router.patch("/{id}/submit")
def submmit_answer_api(id: int, subbmition: Submition, session: Session = Depends(get_session)):
    return study_session_services.submit_answer(session, id, user_answers=subbmition.user_answer)

