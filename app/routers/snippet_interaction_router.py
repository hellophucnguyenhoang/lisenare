from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import Learner, get_session
from app.schemas import SnippetInteractionCreate, StatusResponse, StatusType
from app.services import auth_service, snippet_interaction_service

router = APIRouter(
    prefix="/snippet-interactions", tags=["Snippet Interactions"]
)


@router.post("")
def create_interaction(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner | None, Depends(auth_service.decode_token_get_optional_learner)
    ],
    data: SnippetInteractionCreate,
) -> StatusResponse:
    interaction = snippet_interaction_service.create_interaction(
        session=session,
        session_id=data.session_id,
        snippet_id=data.snippet_id,
        interaction_type=data.interaction_type,
        duration=data.duration,
        learner_id=learner.id if learner else None,
    )

    return StatusResponse(
        status=StatusType.SUCCESS,
        message=f"Interaction type {interaction.type} created.",
    )
