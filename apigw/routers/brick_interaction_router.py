from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlmodel import Session

from database import Learner, get_session
from schemas import (
    BrickInteractionCreate,
)
from services import (
    auth_service,
    brick_interaction_service,
)

router = APIRouter(prefix="/brick-interactions", tags=["Brick Interactions"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_interaction(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner | None, Depends(auth_service.decode_token_get_optional_learner)
    ],
    data: BrickInteractionCreate,
) -> Response:
    brick_interaction_service.handle_interaction_and_update_profile(
        session=session,
        data=data,
        learner_id=learner.id if learner else None,
    )
    return Response(status_code=status.HTTP_201_CREATED)
