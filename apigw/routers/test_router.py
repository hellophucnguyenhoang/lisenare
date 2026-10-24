from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from database import get_session
from exceptions import ErrorCode, RequestException
from services import test_service

router = APIRouter(prefix="/test", tags=["Test"])


@router.get("")
def test_api(
    item_id: int | None = None,
):
    credentials_exception = RequestException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        debug_message=f"Could not validate credentials {item_id}",
        error_code=ErrorCode.AUTH_FAILED,
        headers={"WWW-Authenticate": "Bearer"},
    )
    raise credentials_exception


@router.get("/two")
def test_api2(
    session: Annotated[Session, Depends(get_session)],
):
    try:
        test_service.export_bricks_to_csv(session)
    except Exception as e:
        raise e
