from sqlmodel import Session
from app.models import StudySession
from app.schemas import StudySessionCreate
from datetime import datetime, timezone

def record_study_session(session: Session, session_create: StudySessionCreate) -> StudySession:
    study_session = StudySession.model_validate(session_create)
    session.add(study_session)
    session.commit()
    session.refresh(study_session)
    return study_session
