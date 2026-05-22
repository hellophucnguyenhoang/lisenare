from typing import Annotated

from fastapi import Depends, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from sqlalchemy import not_
from sqlmodel import Session, select

from app import security
from app.database import OTP, Account, Learner, get_session
from app.exceptions import ErrorCode, RequestException

from . import account_service, learner_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def authenticate_account(
    session: Session, username: str, password: str
) -> Account:
    account = account_service.get_account_by_username(session, username)
    if not account or not security.verify_password(
        password, account.hashed_password
    ):
        raise RequestException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            debug_message="Incorrect username or password",
            error_code=ErrorCode.INVALID_CREDENTIALS,
            headers={"WWW-Authenticate": "Bearer"},
        )
    return account


async def decode_token_get_learner(
    session: Annotated[Session, Depends(get_session)],
    token: Annotated[str, Depends(oauth2_scheme)],
) -> Learner:
    # One general exception to avoid auth information leak
    credentials_exception = RequestException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        debug_message="Could not validate credentials",
        error_code=ErrorCode.AUTH_FAILED,
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = security.decode_access_token(token)
        learner_id = payload.sub

        if not learner_id:
            raise credentials_exception

    except InvalidTokenError:
        raise credentials_exception

    learner = learner_service.get_learner_by_id(session, learner_id)
    if not learner:
        raise credentials_exception

    return learner


async def decode_token_get_optional_learner(
    session: Annotated[Session, Depends(get_session)],
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> Learner | None:
    try:
        if not token:
            return None

        return await decode_token_get_learner(
            session=session,
            token=token,
        )

    except RequestException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return None

        raise


def get_most_recent_unused_otp(session: Session, email: str) -> OTP:
    otp_db = session.exec(
        select(OTP)
        .where(OTP.email == email, not_(OTP.used))
        .order_by(OTP.expires_at.desc())
    ).first()
    return otp_db
