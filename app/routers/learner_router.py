from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import Learner, get_session
from app.schemas import LearnerDetailRead, LearnerRead, LearnerUpdate
from app.services import auth_service, learner_service

router = APIRouter(prefix="/learners", tags=["Learners"])


@router.get("/me", response_model=LearnerDetailRead)
def get_learner_me(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
):
    db_learner = session.get(Learner, learner.id) or learner
    email = db_learner.account.email if db_learner.account else None
    return LearnerDetailRead(
        id=db_learner.id,
        name=db_learner.name,
        email=email,
        practice_lang=db_learner.practice_lang,
    )


@router.patch("/me", response_model=LearnerRead)
def update_learner_me(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    data: LearnerUpdate,
):
    updated = learner_service.update_learner(
        session=session,
        learner=learner,
        data=data,
    )
    return updated
