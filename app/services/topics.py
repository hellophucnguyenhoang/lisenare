from sqlmodel import Session, select
from app.models import Topic
from typing import List


def create_topic(session: Session, name: str) -> Topic:
    topic = Topic(name=name)
    session.add(topic)
    session.commit()
    session.refresh(topic)
    return topic


def get_all_topics(session: Session) -> List[Topic]:
    topics = session.exec(select(Topic)).all()
    return topics


def get_topic_by_id(session: Session, topic_id: int) -> Topic | None:
    return session.get(Topic, topic_id)


def get_topic_by_name(session: Session, name: str) -> Topic | None:
    return session.exec(select(Topic).where(Topic.name == name)).first()
