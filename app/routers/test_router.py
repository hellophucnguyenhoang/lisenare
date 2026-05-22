from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.database import get_session
from app.exceptions import ErrorCode, RequestException
from app.services import test_service

router = APIRouter(prefix="/test", tags=["Test"])


@router.get("")
def create_exception():
    raise RequestException(
        status_code=status.HTTP_400_BAD_REQUEST,
        error_code=ErrorCode.INVALID_CREDENTIALS,
        debug_message="Bad Credential",
    )


@router.get("/a")
def create_exception2():
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("export")
def export_bricks(session: Annotated[Session, Depends(get_session)]):
    test_service.export_bricks_to_csv(session)
    return {"message": "export bricks"}
