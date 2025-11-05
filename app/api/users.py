# app/api/users.py
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError

from app.database import get_session
from app.services import users as user_service
from app.schemas import UserCreate, UserRead, UserWithToken, Token
from app.core.security import decode_access_token, create_access_token

router = APIRouter(prefix="/users", tags=["Users"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

@router.post("/", response_model=UserWithToken)
def register_user(user: UserCreate, session: Session = Depends(get_session)):
    existing = user_service.get_user_by_username(session, user.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")
    new_user = user_service.create_user(session, user)
    access_token = create_access_token({"sub": new_user.username})
    return {"user": new_user, "token": Token(access_token=access_token)}

@router.get("/me", response_model=UserRead)
def read_users_me(token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)):
    try:
        payload = decode_access_token(token)
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = user_service.get_user_by_username(session, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
