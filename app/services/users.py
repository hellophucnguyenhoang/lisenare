# app/services/users.py
from sqlmodel import Session, select
from app.models import User
from app.schemas import UserCreate
from app.security import get_password_hash
from . import readings as reading_service
from . import item_embeddings as item_embedding_service
import numpy as np

def create_user(session: Session, user_create: UserCreate) -> User:
    hashed_password = get_password_hash(user_create.password)
    user = User(
        username=user_create.username,
        email=user_create.email,
        hashed_password=hashed_password,
        # TODO: cần cải thiện sau: khởi tạo theo sở thích đã chọn của user
        preference_emb=item_embedding_service.init_user_embedding(session)
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_user_by_username(session: Session, username: str):
    return session.exec(select(User).where(User.username == username)).first()

def get_user_by_id(session: Session, user_id: int):
    return session.exec(select(User).where(User.id == user_id)).first()
