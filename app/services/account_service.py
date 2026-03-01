from fastapi import BackgroundTasks, HTTPException, status
from sqlmodel import select, Session
from email.message import EmailMessage
import smtplib

from app.database import Account, Learner
from app.schemas import LearnerAccountCreate
from app import security
from app.config import settings


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
