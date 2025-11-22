from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.database import get_session
from app.services import topics as topic_service
from app.schemas import TopicRead

router = APIRouter(prefix="/topics", tags=["Topics"])

@router.get("/all", response_model=list[TopicRead])
def get_all_topics_api(session: Session = Depends(get_session)):
    return topic_service.get_all_topics(session)

@router.get("/by-ids", response_model=list[TopicRead])
def get_topics_by_ids_api(ids: list[int] = Query(...), session: Session = Depends(get_session)):
    return topic_service.get_topics_by_ids(session, topic_ids=ids)
