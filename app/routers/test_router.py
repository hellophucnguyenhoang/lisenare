from fastapi import APIRouter, Depends
from sqlmodel import Session
from typing import Annotated

from app.database import get_session
from app.services import collection_service


router = APIRouter(prefix="/test", tags=["A"])


@router.get("")
def test(
    session: Annotated[Session, Depends(get_session)],
):
    return collection_service.temp_test(session)
