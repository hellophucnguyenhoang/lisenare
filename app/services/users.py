from sqlmodel import Session, select
from app.models import User, UserTopicLink
from app.schemas import UserCreate
from typing import Optional, List
from datetime import datetime, timezone

def create_user(session: Session, user_create: UserCreate) -> User:
    password_hash = user_create.password + "hashed"
    user = User.model_validate(user_create, update={"password_hash": password_hash})
    user.password_hash = password_hash
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

def get_user_by_username(session: Session, username: str) -> Optional[User]:
    return session.exec(select(User).where(User.username == username)).first()

def link_user_to_topics(session: Session, user_id: int, topic_ids: List[int]):
    for topic_id in topic_ids:
        session.add(UserTopicLink(user_id=user_id, topic_id=topic_id))
    session.commit()
