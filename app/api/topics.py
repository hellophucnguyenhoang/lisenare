from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List

from app.database import get_session
from app.schemas import TopicCreate, TopicRead
from app.services import topics as topic_service

router = APIRouter(prefix="/topics", tags=["Topics"])

# -------------------
# Create a new topic
# -------------------
@router.post("/", response_model=TopicRead)
def create_topic_api(topic: TopicCreate, session: Session = Depends(get_session)):
    return topic_service.create_topic(session, topic.name)

# -------------------
# Get all topics
# -------------------
@router.get("/", response_model=List[TopicRead])
def list_topics_api(session: Session = Depends(get_session)):
    return topic_service.get_all_topics(session)

# -------------------
# Get a topic by ID
# -------------------
@router.get("/{topic_id}", response_model=TopicRead)
def get_topic_by_id_api(topic_id: int, session: Session = Depends(get_session)):
    topic = topic_service.get_topic_by_id(session, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic

# -------------------
# Get a topic by name
# -------------------
@router.get("/by-name/{name}", response_model=TopicRead)
def get_topic_by_name_api(name: str, session: Session = Depends(get_session)):
    topic = topic_service.get_topic_by_name(session, name)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic
