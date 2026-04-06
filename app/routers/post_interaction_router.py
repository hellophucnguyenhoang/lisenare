from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import Learner, get_session
from app.schemas import InteractionCreate, StatusResponse
from app.services import auth_service, post_interaction_service

router = APIRouter(prefix="/interactions", tags=["Interactions"])


@router.patch("", response_model=StatusResponse)
def upsert_interaction(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    data: InteractionCreate,
):
    interaction = post_interaction_service.create_or_update_interaction(
        session=session,
        learner_id=learner.id,
        post_id=data.post_id,
        reward=data.reward,
    )
    return {"status": "success", "message": f"Reward {interaction.reward}"}
