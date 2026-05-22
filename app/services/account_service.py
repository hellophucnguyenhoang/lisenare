import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage

from fastapi import BackgroundTasks, status
from sqlmodel import Session, or_, select

from app import security
from app.config import settings
from app.database import Account, Learner
from app.exceptions import ErrorCode, RequestException
from app.schemas import (
    LearnerAccountCreate,
    PasswordResetRequest,
)
from app.services import auth_service


def get_account_by_username(session: Session, username: str) -> Account:
    statement = select(Account).where(Account.username == username)
    return session.exec(statement).first()


def create_learner_account(
    session: Session, learner_account_create: LearnerAccountCreate
) -> Account:
    existing_account = session.scalars(
        select(Account).where(
            or_(
                Account.email == learner_account_create.email,
                Account.username == learner_account_create.username,
            )
        )
    ).first()

    if existing_account:
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message="Username or email registration conflicts.",
            error_code=ErrorCode.USERNAME_OR_EMAIL_TAKEN,
        )

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
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=f"Account for {learner_id=} not found",
        )
    if not security.verify_password(old_password, account.hashed_password):
        raise RequestException(
            status_code=status.HTTP_403_FORBIDDEN,
            debug_message="Wrong old password",
            error_code=ErrorCode.INCORRECT_PASSWORD,
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


def reset_account_password(session: Session, request: PasswordResetRequest):
    account = get_account_by_username(session, request.username)
    if not account:
        raise RequestException(
            status_code=status.HTTP_404_NOT_FOUND,
            debug_message=(
                f"Account not found for username={request.username}"
            ),
            error_code=ErrorCode.ACCOUNT_NOT_FOUND,
        )

    if not account.email:
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message=(
                f"Account username={request.username} does not have an email"
            ),
            error_code=ErrorCode.ACCOUNT_HAS_NO_EMAIL,
        )

    otp_entry = auth_service.get_most_recent_unused_otp(session, account.email)

    if not otp_entry:
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message=(f"No valid OTP found for email={account.email}"),
            error_code=ErrorCode.OTP_NOT_FOUND,
        )

    if otp_entry.expires_at.replace(tzinfo=timezone.utc) < datetime.now(
        timezone.utc
    ):
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message=(f"Expired OTP for email={account.email}"),
            error_code=ErrorCode.OTP_EXPIRED,
        )

    if not security.verify_otp(request.otp, otp_entry.hashed_code):
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message=(f"Invalid OTP for email={account.email}"),
            error_code=ErrorCode.INVALID_OTP,
        )

    otp_entry.used = True
    account.hashed_password = security.get_password_hash(request.new_password)

    session.add(otp_entry)
    session.add(account)
    session.commit()
