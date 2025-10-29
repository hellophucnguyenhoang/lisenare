from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.database import get_session
from app.schemas import UserRead, UserCreate
from app.models import User
from app.services import users as user_service

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/", response_model=UserRead)
def create_user_api(user: UserCreate, session: Session = Depends(get_session)):
    return user_service.create_user(session, user)

@router.get("/by-username/{username}", response_model=UserRead)
def get_user_by_username_api(username: str, session: Session = Depends(get_session)):
    user = user_service.get_user_by_username(session, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

