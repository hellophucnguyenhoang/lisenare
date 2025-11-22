# app/services/auth.py
from fastapi import HTTPException, status
from sqlmodel import Session, select
from datetime import timedelta
from app.services.users import get_user_by_username
from app.security import verify_password, create_access_token
from app.schemas import Token
from app.models import OTP
from app.config import settings
import smtplib
from email.message import EmailMessage
from fastapi import BackgroundTasks


def authenticate_user(session: Session, username: str, password: str):
    user = get_user_by_username(session, username)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user

def login_for_access_token(session: Session, username: str, password: str) -> Token:
    user = authenticate_user(session, username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)
    return Token(access_token=access_token, token_type="bearer")


def send_email(to_email: str, subject: str, body: str):
    EMAIL_ADDRESS = settings.google_app_email_address
    EMAIL_PASSWORD = settings.google_app_password

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email
    msg.set_content(body)

    # Connect to Gmail SMTP server
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

    print(f"Email sent to {to_email}")

def send_email_background(background_tasks: BackgroundTasks, to_email: str, otp: str):
    background_tasks.add_task(send_email, to_email, "Your OTP Code", f"Your OTP is: {otp}")


def get_most_recent_unused_otp(session: Session, email: str):
    # Get the most recent unused OTP for this email
    otp_entry = session.exec(
        select(OTP)
        .where(OTP.email == email, OTP.used == False)
        .order_by(OTP.expires_at.desc())
    ).first()
    return otp_entry