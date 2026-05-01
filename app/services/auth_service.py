from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from sqlalchemy import not_
from sqlmodel import Session, select

from app import security
from app.database import OTP, Account, Learner, get_session

from . import account_service, learner_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def authenticate_account(
    session: Session, username: str, password: str
) -> Account:
    account = account_service.get_account_by_username(session, username)
    if not account or not security.verify_password(
        password, account.hashed_password
    ):
        return None
    return account


async def decode_token_get_learner(
    session: Annotated[Session, Depends(get_session)],
    token: Annotated[str, Depends(oauth2_scheme)],
) -> Learner:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = security.decode_access_token(token)
        learner_id = payload.sub
        if not learner_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Not found learner_id in the sub of the token",
            )
    except InvalidTokenError:
        raise credentials_exception
    learner = learner_service.get_learner_by_id(session, learner_id)
    if not learner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learner not found for learner_id",
        )
    return learner


async def decode_token_get_optional_learner(
    session: Annotated[Session, Depends(get_session)],
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> Learner | None:
    try:
        if not token:
            return None
        return await decode_token_get_learner(session=session, token=token)
    except HTTPException:
        return None


def get_most_recent_unused_otp(session: Session, email: str) -> OTP:
    otp_db = session.exec(
        select(OTP)
        .where(OTP.email == email, not_(OTP.used))
        .order_by(OTP.expires_at.desc())
    ).first()
    return otp_db
