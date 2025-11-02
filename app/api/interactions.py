# app/routers/interactions.py
from fastapi import APIRouter, Depends, status, HTTPException
from sqlmodel import Session
from datetime import datetime
from typing import List
import logging

from app.database import get_session
from app.schemas import InteractionCreate
from app.models import Interaction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interactions", tags=["Interactions"])

@router.post("/", status_code=status.HTTP_204_NO_CONTENT)
def create_interactions(
    events: List[InteractionCreate],
    session: Session = Depends(get_session)
):
    try:
        # validate input list length
        if not events:
            raise HTTPException(status_code=400, detail="No events provided")

        for ev in events:
            session.add(
                Interaction(
                    user_id=ev.user_id,
                    item_id=ev.item_id,
                    event_type=ev.event_type,
                    event_time=ev.event_time or datetime.utcnow(),
                    metadata=ev.metadata,
                )
            )

        session.commit()

    except HTTPException:
        # known validation problem → let FastAPI show it to client
        session.rollback()
        raise

    except Exception as e:
        # unknown internal bug → rollback and log for investigation
        session.rollback()
        logger.exception(f"Error saving interactions: {e}")
        # Return 202 to not block client, but note server accepted input
        return {"status": "accepted_with_error_logged"}
