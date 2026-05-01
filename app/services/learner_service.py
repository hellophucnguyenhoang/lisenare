from sqlmodel import Session, select

from app.database import Learner


def get_learner_by_id(session: Session, id: int) -> Learner:
    statement = select(Learner).where(Learner.id == id)
    return session.exec(statement).first()
