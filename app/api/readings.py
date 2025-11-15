from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import get_session
from app.schemas import ReadingRead
from app.services import readings as reading_service

router = APIRouter(prefix="/readings", tags=["Readings"])

@router.get("/full-by-id/{id}", response_model=ReadingRead)
def list_topics_api(id: int, session: Session = Depends(get_session)):
    reading = reading_service.get_full_reading_by_id(session, id)
    return reading