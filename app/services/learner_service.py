from sqlmodel import select, Session

from app.database import Learner


def get_learner_by_id(session: Session, id: int) -> Learner:
    statement = select(Learner).where(Learner.id == id)
    return session.exec(statement).first()


def get_detailed_learner_by_id(session: Session, id: int):
    pass
