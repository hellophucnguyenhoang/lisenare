from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import Learner, get_session
from app.schemas import LearningCardStats
from app.services import auth_service, learning_card_service

router = APIRouter(prefix="/learning-cards", tags=["Learning Cards"])


@router.get("/stats", response_model=LearningCardStats)
def get_learning_stats(
    session: Annotated[Session, Depends(get_session)],
    current_learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
):
    return learning_card_service.get_learning_stats(
        session, current_learner.id
    )
