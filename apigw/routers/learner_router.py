from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from sqlmodel import Session

from constants import LEARNER_AVATARS_DIR
from database import Learner, get_session
from schemas import (
    LearnerDetailRead,
    LearnerRead,
    LearnerUpdate,
)
from services import auth_service, learner_service
from utils import file_utils

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
        retrieval_lang=db_learner.retrieval_lang,
        avatar_path=db_learner.avatar_path,
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


@router.patch("/me/avatar", response_model=LearnerRead)
async def update_learner_avatar(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    avatar_file: Annotated[UploadFile, File()],
):
    avatar_path = await file_utils.process_and_save_image(
        file=avatar_file,
        relative_path=LEARNER_AVATARS_DIR / f"learner-{learner.id}",
        filename_prefix="avatar",
    )

    return learner_service.update_learner_avatar(
        session=session,
        learner=learner,
        avatar_path=avatar_path,
    )


@router.post("/avatar")
def get_learner_avatar(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
) -> str:
    return learner_service.get_learner_avatar_url(
        session=session,
        learner_id=learner.id,
    )
