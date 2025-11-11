# app/services/users.py
from sqlmodel import Session, select
from app.models import User, RecommendationState
from app.schemas import UserCreate
from app.core.security import get_password_hash
from . import recommendation_states as recommendation_state_service
from . import readings as reading_service
from . import item_embeddings as item_embedding_service
import numpy as np
from reading_rec_env import get_updated_user_state


def create_user(session: Session, user_create: UserCreate) -> User:
    hashed_password = get_password_hash(user_create.password)
    user = User(
        username=user_create.username,
        email=user_create.email,
        hashed_password=hashed_password,
        # cần cải thiện sau: khởi tạo theo sở thích đã chọn của user
        user_state_emb=item_embedding_service.get_random_embedding(session)
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_user_by_username(session: Session, username: str):
    return session.exec(select(User).where(User.username == username)).first()

def get_user_by_id(session: Session, user_id: int):
    return session.exec(select(User).where(User.id == user_id)).first()

def refresh_and_get_user(session: Session, user_id: int, interacted_only: bool):
    """
    Update user to the true state they actually are based on their latest interactions.
    """
    # get the current (might be outdate) user state
    user = get_user_by_id(session=session, user_id=user_id)

    latest_rs = recommendation_state_service.get_latest_recommendation_state(session, user_id, interacted_only)

    if not latest_rs or not latest_rs.item_ids.strip(): # new user with no interactions
        return user

    item_ids = [int(x.strip()) for x in latest_rs.item_ids.split(",") if x.strip().isdigit()]
    reading_embeddings, _ = item_embedding_service.get_all_item_embeddings(session)
    updated_state = get_updated_user_state(
        recent_items = item_ids,
        item_embeddings = reading_embeddings,
        current_user_state_emb = np.frombuffer(user.user_state_emb, dtype=np.float32),
    )
    user.user_state_emb = updated_state.tobytes()
    session.add(user)
    session.commit()
    session.refresh(user)
    return user