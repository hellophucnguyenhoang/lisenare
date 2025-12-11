from pydantic import BaseModel
from typing import Optional, Dict
from redis_client import r
from app.schemas import EventCreate
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_session

router = APIRouter(prefix="/feedback", tags=["User FeedBack"])

@router.post("/event")
def create_event(event: EventCreate, db: Session = Depends(get_session)):
    r.rpush("event_queue", event.model_dump_json())
    print(event)
    return {"status": "ok"}
