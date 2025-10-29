from sqlmodel import Session
from app.models import StudySession
from datetime import datetime, timezone

def record_study_session(session: Session, session_entry: StudySession) -> StudySession:
    session.add(session_entry)
    session.commit()
    session.refresh(session_entry)
    return session_entry
