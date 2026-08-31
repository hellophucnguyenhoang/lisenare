from fastapi import APIRouter, status

from app.exceptions import ErrorCode, RequestException

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
def test_api2():
    try:
        n = 2 / 0
        return n
    except Exception as e:
        raise e
