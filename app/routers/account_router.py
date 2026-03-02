from fastapi import APIRouter, Depends, BackgroundTasks, Body
from sqlmodel import Session

from app import security
from app.schemas import (
    Token,
    PasswordChangeRequest,
    PasswordResetRequest,
    StatusResponse,
)
from app.database import get_session, Learner
from app.services import account_service, auth_service, otp_service
from app.schemas import LearnerAccountCreate, PasswordRecoveryResponse
from app.config import settings

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.post("", response_model=Token)
def create_account(
    learner_account_create: LearnerAccountCreate,
    session: Session = Depends(get_session),
) -> Token:
    account = account_service.create_learner_account(
        session, learner_account_create
    )
    data = {"sub": str(account.learner_id), "username": account.username}
    access_token = security.create_access_token(data=data)
    return Token(access_token=access_token)


@router.patch("/me/password", response_model=Token)
def change_account_password(
    change_password_request: PasswordChangeRequest,
    learner: Learner = Depends(auth_service.decode_token_to_get_learner),
    session: Session = Depends(get_session),
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


@router.post("/forgot-password", response_model=PasswordRecoveryResponse)
def forgot_password(
    background_tasks: BackgroundTasks,
    username: str = Body(embed=True),
    session: Session = Depends(get_session),
):
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

    return {
        "message": "If an account exists, a recovery code has been sent.",
        "email_preview": None,
    }


@router.post("/reset-password", response_model=StatusResponse)
def reset_password(
    password_reset_request: PasswordResetRequest,
    session: Session = Depends(get_session),
):
    return account_service.reset_account_password(
        session, password_reset_request
    )
