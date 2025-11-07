# app/services/users.py
from sqlmodel import Session, select
from app.models import User, UserState
from app.schemas import UserCreate
from app.core.security import get_password_hash
from . import interactions as interaction_service
from . import user_states as user_state_service
from . import readings as reading_service
from . import item_embeddings as item_embedding_service
import numpy as np

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

def get_interacted_items(session: Session, username: str, include_future: bool) -> list[int]:
    # Find the user by username
    user = session.exec(select(User).where(User.username == username)).one()

    current_user_state = user_state_service.get_latest_user_state(session, user.id, include_future)
    if not current_user_state or not current_user_state.item_ids.strip():
        return []

    item_ids = [int(x.strip()) for x in current_user_state.item_ids.split(",") if x.strip().isdigit()]
    return item_ids

def get_current_state(session: Session, username: str, include_future: bool = False) -> np.ndarray:
    item_ids = get_interacted_items(session, username, include_future)
    
    if not item_ids:
        return np.zeros((384,))  # Assuming embedding size is 384

    discount_factor = 0.5
    current_state = None

    # Iterate from oldest → newest
    for item_id in item_ids:
        # get_item_embedding_by_reading_id(session, 1)
        emb = item_embedding_service.get_item_embedding_by_reading_id(session, item_id)

        if emb is None:
            continue

        if current_state is None:
            current_state = emb
        else:
            current_state = emb + current_state * discount_factor

    # Optional: normalize the final state vector to unit length
    if current_state is not None:
        norm = np.linalg.norm(current_state)
        if norm > 0:
            current_state = current_state / norm

    return current_state


def update_user_state(session: Session, username: str, item_id: int):
    """
    Append a new item_id to the user's state sequence.
    If user or user_state doesn't exist, it will create them.
    """
    # 1️⃣ Get user
    user = session.exec(select(User).where(User.username == username)).first()
    if not user:
        raise ValueError(f"User '{username}' not found.")

    # 2️⃣ Get or create user_state
    user_state = session.exec(select(UserState).where(UserState.user_id == user.id)).first()
    if not user_state:
        user_state = UserState(user_id=user.id, item_ids=str(item_id))
        session.add(user_state)
        session.commit()
        session.refresh(user_state)
        return user_state

    # 3️⃣ Append new item_id to the list
    current_ids = [x.strip() for x in user_state.item_ids.split(",") if x.strip()]
    current_ids.append(str(item_id))
    user_state.item_ids = ",".join(current_ids)

    # 4️⃣ Commit changes
    session.add(user_state)
    session.commit()
    session.refresh(user_state)

    return user_state