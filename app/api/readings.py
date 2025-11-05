from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List

from app.database import get_session
from app.schemas import ReadingRead, ReadingCreate
from app.services import readings as reading_service

router = APIRouter(prefix="/readings", tags=["Readings"])

@router.get("/", response_model=List[ReadingRead])
def list_topics_api(session: Session = Depends(get_session)):
    return reading_service.get_all_readings(session)

@router.get("/full-by-id/{id}", response_model=ReadingRead)
def list_topics_api(id: int, session: Session = Depends(get_session)):
    return reading_service.get_full_reading_by_id(session, id)
