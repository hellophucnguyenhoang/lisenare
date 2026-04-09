import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage

from fastapi import BackgroundTasks, HTTPException, status
from sqlmodel import Session, select

from app import security
from app.config import settings
from app.database import Account, Learner
from app.schemas import (
    LearnerAccountCreate,
    PasswordResetRequest,
    StatusResponse,
    StatusType,
)
from app.services import auth_service


def get_account_by_username(session: Session, username: str) -> Account:
    statement = select(Account).where(Account.username == username)
    return session.exec(statement).first()


def create_learner_account(
    session: Session, learner_account_create: LearnerAccountCreate
) -> Account:
    learner = Learner(full_name=learner_account_create.full_name)
    hashed_password = security.get_password_hash(
        learner_account_create.password
    )
    account = Account(
        username=learner_account_create.username,
        hashed_password=hashed_password,
        email=learner_account_create.email,
        learner=learner,
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def change_learner_account_password(
    session: Session, learner_id: int, old_password: str, new_password: str
) -> Account:
    account = session.exec(
        select(Account).where(Account.learner_id == learner_id)
    ).first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )
    if not security.verify_password(old_password, account.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The old password is wrong",
        )
    hashed_new_password = security.get_password_hash(new_password)
    account.hashed_password = hashed_new_password
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def send_email(to_email: str, subject: str, body: str):
    EMAIL_ADDRESS = settings.google_app_email_address
    EMAIL_PASSWORD = settings.google_app_password
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)
    print(f"Email sent to {to_email}")


def send_email_background(
    background_tasks: BackgroundTasks, to_email: str, subject: str, body: str
):
    background_tasks.add_task(send_email, to_email, subject, body)


def reset_account_password(
    session: Session, request: PasswordResetRequest
) -> StatusResponse:
    account = get_account_by_username(session, request.username)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Account not found"
        )

    if not account.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account does not have an email",
        )

    otp_entry = auth_service.get_most_recent_unused_otp(session, account.email)

    if not otp_entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid OTP found",
        )

    if otp_entry.expires_at.replace(tzinfo=timezone.utc) < datetime.now(
        timezone.utc
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="OTP expired"
        )

    if not security.verify_otp(request.otp, otp_entry.hashed_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP"
        )

    otp_entry.used = True
    account.hashed_password = security.get_password_hash(request.new_password)

    session.add(otp_entry)
    session.add(account)
    session.commit()
    return {
        "status": StatusType.SUCCESS,
        "message": "Password has been reset successfully.",
    }
