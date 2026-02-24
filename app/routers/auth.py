"""
The reason why do we have a separate auth group of endpoint here 
while it's mostly do things with account is because 
this authentication can be a third-party application.
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from app.schemas import Token
from sqlmodel import Session
from app.database import get_session, OTP
from app.services import auth_service, account_service, otp_service
from app import security
from datetime import datetime, timezone, timedelta
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    session: Session = Depends(get_session)
) -> Token:
    account = auth_service.authenticate_account(session, form_data.username, form_data.password)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    data = {
        "sub": str(account.learner_id),
        "username": account.username
    }
    access_token = security.create_access_token(data=data)
    return Token(access_token=access_token)

@router.post("/request-otp")
def request_otp(
    background_tasks: BackgroundTasks,
    username: str,
    session: Session = Depends(get_session)
):
    account = account_service.get_account_by_username(session, username)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if not account.email:
        raise HTTPException(status_code=400, detail="This account does not have an email to receive OTP")
    code = otp_service.create_otp(session, account.email)
    subject = "Your OTP Code from Lisenare"
    body = (
        f"Hello, {account.learner.full_name}!\n\n"
        f"Your verification code is: {code}\n"
        f"This code expires in {settings.otp_expire_minutes} minutes.\n\n"
        f"Lisenare team."
    )
    account_service.send_email_background(background_tasks, account.email, subject, body)
    return {"email": account.email}
