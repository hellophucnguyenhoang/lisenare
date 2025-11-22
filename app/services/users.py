# app/services/users.py
from sqlmodel import Session, select
from app.models import User
from app.schemas import UserCreate
from app.security import get_password_hash
from . import topics as topic_service
from . import item_embeddings as item_embedding_service

def create_user(session: Session, user_create: UserCreate) -> User:
    hashed_password = get_password_hash(user_create.password)
    user = User(
        username=user_create.username,
        email=user_create.email,
        hashed_password=hashed_password,
        user_level=user_create.user_level,
        goal_type=user_create.goal_type,
        age_group=user_create.age_group,
        # TODO: cần cải thiện sau: khởi tạo theo sở thích đã chọn của user
        preference_emb=item_embedding_service.init_user_embedding_by_level(session, user_level=user_create.user_level).tobytes()
    )
    user.preference_topics = topic_service.get_topics_by_ids(session, user_create.preference_topic_ids)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_user_by_username(session: Session, username: str):
    return session.exec(select(User).where(User.username == username)).first()

def get_user_by_id(session: Session, user_id: int):
    return session.exec(select(User).where(User.id == user_id)).first()
