# app/services/interactions.py
from sqlmodel import Session, select
from app.models import Interaction, UserState
from app.core.security import get_password_hash

def get_latest_interaction(session: Session, user_id: int):
    stmt = (
        select(Interaction)
        .join(UserState)
        .where(UserState.user_id == user_id)
        .order_by(Interaction.event_time.desc())
    )
    return session.exec(stmt).first()
