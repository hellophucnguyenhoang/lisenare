from sqlmodel import Session, select
from app.models import User, UserState

# app/services/user_states.py
from sqlmodel import Session, select, func
from app.models import Interaction, UserState
from app.core.security import get_password_hash

def get_latest_user_state(session: Session, user_id: int, include_future: bool = False):
    if include_future:
        stmt = (
            select(UserState)
            .where(UserState.user_id == user_id)
            .order_by(func.LENGTH(UserState.item_ids).desc())
        )
    else:
        stmt = (
            select(UserState)
            .join(Interaction)
            .where(UserState.user_id == user_id)
            .order_by(Interaction.event_time.desc())
        )
    return session.exec(stmt).first()


def create_user_state(session: Session, username: str, item_id: int, include_future: bool = True):
    """
    Append a new item_id to the user's state sequence.
    If user or user_state doesn't exist, it will create them.
    """
    user = session.exec(select(User).where(User.username == username)).first()
    if not user:
        raise ValueError(f"User '{username}' not found.")

    user_state = get_latest_user_state(session, user.id, include_future=include_future)
    if not user_state:
        user_state = UserState(user_id=user.id, item_ids=str(item_id))
        session.add(user_state)
        session.commit()
        session.refresh(user_state)
        return user_state

    latest_item_ids = user_state.item_ids
    current_ids = [x.strip() for x in latest_item_ids.split(",")]
    current_ids.append(str(item_id))
    new_user_state = UserState(user_id=user.id, item_ids=",".join(current_ids))

    # Commit changes
    session.add(new_user_state)
    session.commit()
    session.refresh(new_user_state)

    return new_user_state