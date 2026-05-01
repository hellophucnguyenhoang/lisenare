from typing import Annotated

from fastapi import APIRouter, Depends

from app.database import Learner
from app.schemas import LearnerRead
from app.services import auth_service

router = APIRouter(prefix="/learners", tags=["Learners"])


@router.get("/me", response_model=LearnerRead)
def get_learner_me(
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
):
    return learner
