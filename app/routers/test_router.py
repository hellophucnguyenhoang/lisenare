from fastapi import APIRouter, Depends, File, UploadFile
from sqlmodel import Session, SQLModel
from typing import Annotated

from app.database import get_session
from app.services import test_service


router = APIRouter(prefix="/test", tags=["A"])


@router.post("")
def export_bricks(session: Annotated[Session, Depends(get_session)]):
    test_service.export_bricks_to_csv(session)
    return {"message": "export bricks"}
