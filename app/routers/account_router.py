from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Response, status
from sqlmodel import Session

from app import security
from app.database import Learner, get_session
from app.schemas import (
    EmailChangeOTPRequest,
    EmailChangeRequest,
    LearnerAccountCreate,
    PasswordChangeRequest,
    PasswordResetRequest,
    SendOTPRequest,
    Token,
)
from app.services import account_service, auth_service

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.post("")
def create_account(
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    learner_account_create: LearnerAccountCreate,
) -> Token:
    account = account_service.create_learner_account(
        session, learner_account_create
    )
    data = {"sub": str(account.learner_id), "username": account.username}
    access_token = security.create_access_token(data=data)
    security.set_access_token(response, access_token)
    return Token(access_token=access_token)


@router.post("/send-otp", status_code=status.HTTP_204_NO_CONTENT)
async def send_otp(
    session: Annotated[Session, Depends(get_session)],
    background_tasks: BackgroundTasks,
    request: SendOTPRequest,
) -> Response:
    account_service.send_otp_by_username(
        session, background_tasks, request.username
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    session: Annotated[Session, Depends(get_session)],
    password_reset_request: PasswordResetRequest,
) -> Response:
    account_service.reset_account_password(session, password_reset_request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/password")
def change_account_password(
    response: Response,
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
    security.set_access_token(response, access_token)
    return Token(access_token=access_token)


@router.post("/email/send-otp", status_code=status.HTTP_204_NO_CONTENT)
async def send_email_change_otp(
    session: Annotated[Session, Depends(get_session)],
    background_tasks: BackgroundTasks,
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    request: EmailChangeOTPRequest,
) -> Response:
    account_service.send_email_change_otp(
        session, background_tasks, learner.id, request
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/email", status_code=status.HTTP_204_NO_CONTENT)
def change_account_email(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    email_change_request: EmailChangeRequest,
) -> Response:
    account_service.change_learner_account_email(
        session,
        learner_id=learner.id,
        request=email_change_request,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
