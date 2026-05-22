from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Response, status
from sqlmodel import Session

from app import security
from app.config import settings
from app.database import Learner, get_session
from app.schemas import (
    LearnerAccountCreate,
    PasswordChangeRequest,
    PasswordRecoveryResponse,
    PasswordResetRequest,
    Token,
)
from app.services import account_service, auth_service, otp_service

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.post("")
def create_account(
    session: Annotated[Session, Depends(get_session)],
    learner_account_create: LearnerAccountCreate,
) -> Token:
    account = account_service.create_learner_account(
        session, learner_account_create
    )
    data = {"sub": str(account.learner_id), "username": account.username}
    access_token = security.create_access_token(data=data)
    return Token(access_token=access_token)


@router.post("/forgot-password")
def forgot_password(
    session: Annotated[Session, Depends(get_session)],
    background_tasks: BackgroundTasks,
    username: Annotated[str, Body(embed=True)],
) -> PasswordRecoveryResponse:
    account = account_service.get_account_by_username(session, username)
    if account and account.email:
        code = otp_service.create_otp(session, account.email)
        subject = "Your OTP Code from Lisenare"
        body = (
            f"Hello!\n\n"
            f"Your verification code is: {code}\n"
            f"This code expires in {settings.otp_expire_minutes} minutes.\n\n"
            f"Lisenare team."
        )
        account_service.send_email_background(
            background_tasks, account.email, subject, body
        )

    return PasswordRecoveryResponse(
        message="If an account exists, a recovery code has been sent.",
        email_preview=None,
    )


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    session: Annotated[Session, Depends(get_session)],
    password_reset_request: PasswordResetRequest,
) -> Response:
    account_service.reset_account_password(session, password_reset_request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/me/password")
def change_account_password(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    change_password_request: PasswordChangeRequest,
) -> Token:
    account = account_service.change_learner_account_password(
        session,
        learner_id=learner.id,
        old_password=change_password_request.old_password,
        new_password=change_password_request.new_password,
    )
    data = {"sub": str(account.learner_id), "username": account.username}
    access_token = security.create_access_token(data=data)
    return Token(access_token=access_token)
