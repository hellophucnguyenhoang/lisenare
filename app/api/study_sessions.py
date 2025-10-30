# app/api/study_sessions.py
from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.database import get_session
from app.schemas import StudySessionCreate, RatingUpdate, StudySessionResult
from app.services import study_sessions as service

router = APIRouter(prefix="/study_sessions", tags=["StudySessions"])

@router.post("/", response_model=StudySessionResult)
def create_study_session(session_in: StudySessionCreate, db: Session = Depends(get_session)):
    return service.create_study_session(db, session_in)

@router.get("/{session_id}", response_model=StudySessionResult)
def get_study_session_result(session_id: int, db: Session = Depends(get_session)):
    return service.get_study_session_result(db, session_id)

@router.patch("/{session_id}/rating")
def update_rating(session_id: int, payload: RatingUpdate, db: Session = Depends(get_session)):
    return service.update_rating(db, session_id, payload)
