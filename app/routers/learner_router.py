from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import Learner, get_session
from app.schemas import LearnerRead, LearnerUpdateName
from app.services import auth_service, learner_service

router = APIRouter(prefix="/learners", tags=["Learners"])


@router.get("/me", response_model=LearnerRead)
def get_learner_me(
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
):
    return learner


@router.patch("/me", response_model=LearnerRead)
def update_my_name(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    data: LearnerUpdateName,
):
    updated = learner_service.update_learner_full_name(
        session=session,
        learner=learner,
        full_name=data.full_name,
    )
    return updated
