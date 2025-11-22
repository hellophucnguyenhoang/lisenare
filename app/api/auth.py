# app/api/auth.py
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Body
from sqlmodel import Session
from fastapi.security import OAuth2PasswordRequestForm
from app.database import get_session
from app.services import auth as auth_service
from app.services import users as user_service
from app.models import OTP
from app.schemas import Token, UserRead
from app import security
from app.config import settings
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/login", response_model=Token)
def login_api(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    return auth_service.login_for_access_token(session, form_data.username, form_data.password)


@router.post("/request-otp")
def request_otp(
    background_tasks: BackgroundTasks,
    username: str,
    session: Session = Depends(get_session)
):
    user = user_service.get_user_by_username(session, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.email:
        raise HTTPException(status_code=400, detail="User does not have an email to receive OTP")

    # Generate OTP
    code = security.generate_otp()
    hashed = security.hash_otp(code)

    # Create OTP entry
    otp_entry = OTP(
        email=user.email,
        code=hashed,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.otp_expire_minutes)
    )
    session.add(otp_entry)
    session.commit()

    # Email body
    subject = "Your OTP Code from Lisenare"
    body = (
        f"Hello {user.username}!\n\n"
        f"Your Lisenare verification code is: {code}\n"
        f"This code expires in {settings.otp_expire_minutes} minutes.\n\n"
        f"If you didn't request this code, please ignore this email."
    )

    # Send email in background
    background_tasks.add_task(auth_service.send_email, user.email, subject, body)

    return {"email": user.email}


@router.post("/change-password", response_model=UserRead)
def change_password(
    username: str = Body(...),
    otp: str = Body(...),
    new_password: str = Body(...),
    session: Session = Depends(get_session)
):
    user = user_service.get_user_by_username(session, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.email:
        raise HTTPException(status_code=400, detail="User does not have an email")

    # Get the most recent unused OTP for this email
    otp_entry = auth_service.get_most_recent_unused_otp(session, user.email)

    if not otp_entry:
        raise HTTPException(status_code=400, detail="No valid OTP found")

    # Check expiration
    if otp_entry.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="OTP expired")

    # Verify OTP
    if not security.verify_otp(otp, otp_entry.code):
        raise HTTPException(status_code=400, detail="Invalid OTP")

    # Mark OTP as used
    otp_entry.used = True
    session.add(otp_entry)

    # Update password
    user.hashed_password = security.get_password_hash(new_password)
    session.add(user)
    session.commit()
    session.refresh(user)

    return user
