# app/services/users.py
from sqlmodel import Session, select
from app.models import User
from app.schemas import UserCreate
from app.core.security import get_password_hash

def create_user(session: Session, user_create: UserCreate) -> User:
    hashed_password = get_password_hash(user_create.password)
    user = User(
        username=user_create.username,
        email=user_create.email,
        hashed_password=hashed_password,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def get_user_by_username(session: Session, username: str):
    return session.exec(select(User).where(User.username == username)).first()
