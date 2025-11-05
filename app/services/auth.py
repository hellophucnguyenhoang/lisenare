# app/services/auth.py
from fastapi import HTTPException, status
from sqlmodel import Session
from datetime import timedelta
from app.services.users import get_user_by_username
from app.core.security import verify_password, create_access_token
from app.schemas import Token
from app.config import settings

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
