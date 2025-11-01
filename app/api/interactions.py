# app/routers/interactions.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlmodel import Session
from datetime import datetime

from app.database import get_session
from app.schemas import InteractionCreate, InteractionRead
from app.models import Interaction

router = APIRouter(prefix="/interactions", tags=["interactions"])

@router.post("/", response_model=List[InteractionRead])
def create_interactions(events: List[InteractionCreate], session: Session = Depends(get_session)):
    created = []
    try:
        for ev in events:
            # if client didn't send event_time, use now()
            event_time = ev.event_time or datetime.utcnow()
            db_obj = Interaction(
                user_id=ev.user_id,
                item_id=ev.item_id,
                event_type=ev.event_type,
                event_time=event_time,
                metadata=ev.metadata,
            )
            session.add(db_obj)
        session.commit()

        # refresh and return created objects
        for ev in session.exec(Interaction.select().order_by(Interaction.id.desc()).limit(len(events))):
            created.append(ev)
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return created
