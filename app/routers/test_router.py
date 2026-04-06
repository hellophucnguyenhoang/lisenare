from fastapi import APIRouter, Depends
from sqlmodel import Session
from typing import Annotated

from app.database import get_session
from app.services import test_service, brick_service


router = APIRouter(prefix="/test", tags=["A"])


@router.get("")
def get_pending_bricks_collection(
    session: Annotated[Session, Depends(get_session)],
):
    return brick_service.get_pending_bricks(
        session, learner_id=2, collection_id=1097
    )


@router.post("")
def export_bricks(session: Annotated[Session, Depends(get_session)]):
    test_service.export_bricks_to_csv(session)
    return {"message": "export bricks"}
