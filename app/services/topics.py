# app/services/users.py
from sqlmodel import Session, select
from app.models import Topic

def get_all_topics(session: Session):
    return session.exec(select(Topic)).all()

def get_topics_by_ids(session: Session, topic_ids: list[int]):
    if not topic_ids:
        return []
    stmt = select(Topic).where(Topic.id.in_(topic_ids))
    return session.exec(stmt).all()
