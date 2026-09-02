from typing import Annotated

from fastapi import Cookie, Depends, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from sqlalchemy import not_
from sqlmodel import Session, select

from app import security
from app.config import logger
from app.database import OTP, Account, Learner, get_session
from app.exceptions import ErrorCode, RequestException

from . import account_service, learner_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def authenticate_account(
    session: Session, username: str, password: str
) -> Account:
    logger.info(f"Attempting authentication for username: '{username}'")

    account = account_service.get_account_by_username(session, username)
    if not account:
        logger.warning(
            f"Authentication failed: Username '{username}' not found in database."
        )
        raise RequestException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            debug_message="Incorrect username or password",
            error_code=ErrorCode.INVALID_CREDENTIALS,
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not security.verify_password(password, account.hashed_password):
        logger.warning(
            f"Authentication failed: Invalid password provided for username '{username}'."
        )
        raise RequestException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            debug_message="Incorrect username or password",
            error_code=ErrorCode.INVALID_CREDENTIALS,
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info(
        f"Successful password authentication for username: '{username}' (Account ID: {account.id})"
    )
    return account


async def decode_token_get_learner(
    session: Annotated[Session, Depends(get_session)],
    token: Annotated[str | None, Depends(oauth2_scheme)],
    access_token: Annotated[
        str | None,
        Cookie(description="Browser's JS can't touch this cookie"),
    ] = None,
) -> Learner:
    # One general exception to avoid auth information leak
    credentials_exception = RequestException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        debug_message="Could not validate credentials",
        error_code=ErrorCode.AUTH_FAILED,
        headers={"WWW-Authenticate": "Bearer"},
    )

    # prioritize token from Cookie
    if access_token:
        token = access_token

    # block the request when neither provided a token
    if not token:
        logger.warning(
            "Authentication failed: No authentication token found in cookies or headers."
        )
        raise credentials_exception

    try:
        payload = security.decode_access_token(token)
        learner_id = payload.sub

        if not learner_id:
            logger.warning(
                "Authentication failed: Decoded token missing 'sub' claim."
            )
            raise credentials_exception

    except InvalidTokenError as exc:
        logger.warning(
            f"Authentication failed: Invalid JWT token signature or expiration. Details: {exc}"
        )
        raise credentials_exception

    learner = learner_service.get_learner_by_id(session, learner_id)
    if not learner:
        logger.error(
            f"Authentication database discrepancy: Learner ID {learner_id} extracted from token, but not found in DB."
        )
        raise credentials_exception

    logger.info(f"Successfully authenticated learner ID: {learner_id}")
    return learner


async def decode_token_get_optional_learner(
    session: Annotated[Session, Depends(get_session)],
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> Learner | None:
    try:
        if not token:
            logger.debug(
                "Optional authentication called without a token. Proceeding as guest."
            )
            return None

        return await decode_token_get_learner(
            session=session,
            token=token,
        )

    except RequestException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            logger.info(
                "Optional token evaluation resulted in 401 Unauthorized. Downgrading request to guest session."
            )
            return None

        logger.error(
            f"Unexpected RequestException in optional learner evaluation: {exc.debug_message}"
        )
        raise


def get_most_recent_unused_otp(session: Session, email: str) -> OTP:
    logger.info(f"Querying most recent unused OTP for email: '{email}'")

    otp_db = session.exec(
        select(OTP)
        .where(OTP.email == email, not_(OTP.used))
        .order_by(OTP.expires_at.desc())
    ).first()

    if not otp_db:
        logger.warning(
            f"No active or unused OTP tokens available for email: '{email}'"
        )
    else:
        logger.debug(
            f"Retrieved unused OTP ID {otp_db.id} for email '{email}'. (Expires at: {otp_db.expires_at})"
        )

    return otp_db
