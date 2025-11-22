# app/api/users.py
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError

from app.database import get_session
from app.models import User
from app.services import users as user_service
from app.services import topics as topic_service
from app.schemas import UserCreate, UserRead, UserUpdate, UserWithToken, Token
from app.security import decode_access_token, create_access_token
import numpy as np

router = APIRouter(prefix="/users", tags=["Users"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session)
):
    try:
        payload = decode_access_token(token)
        username = payload.get("sub")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = user_service.get_user_by_username(session, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user

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
        print(token)
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

@router.patch("/me", response_model=UserRead)
def update_user_me(
    updates: UserUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    update_data = updates.model_dump(exclude_unset=True)

    # Handle preference_topic_ids separately
    topic_ids = update_data.pop("preference_topic_ids", None)

    # ---- Update normal scalar fields ----
    for field, value in update_data.items():
        setattr(current_user, field, value)

    # ---- Update user preference topics (Many-to-Many) ----
    if topic_ids is not None:
        # Clear existing topics
        current_user.preference_topics.clear()

        if len(topic_ids) > 0:
            # Fetch new topics that exist in DB
            topics = topic_service.get_topics_by_ids(session, topic_ids)

            # Assign them to the relationship
            current_user.preference_topics.extend(topics)

    session.add(current_user)
    session.commit()
    session.refresh(current_user)

    return current_user


