from fastapi import APIRouter, Depends

from app.database import Learner
from app.services import auth_service
from app.schemas import LearnerRead

router = APIRouter(prefix="/learners", tags=["Learners"])


@router.get("/me", response_model=LearnerRead)
def get_learner_me(
    learner: Learner = Depends(auth_service.decode_token_to_get_learner),
):
    return learner
