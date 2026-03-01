from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import get_session, Learner
from app.services import auth_service, learning_card_service
from app.schemas import LearningCardStats


router = APIRouter(prefix="/learning-cards", tags=["Learning Cards"])


@router.get("/stats", response_model=LearningCardStats)
def get_learning_stats(
    current_learner: Learner = Depends(
        auth_service.decode_token_to_get_learner
    ),
    session: Session = Depends(get_session),
):
    return learning_card_service.get_learning_stats(
        session, current_learner.id
    )
