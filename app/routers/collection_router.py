from fastapi import APIRouter, Depends
from sqlmodel import Session
from typing import Annotated

from app.database import get_session, Learner
from app.services import (
    auth_service,
    collection_service,
    brick_override_service,
)
from app.schemas import (
    CollectionCreate,
    CollectionRead,
    GroupStats,
    OverrideGroupsCreate,
    OverrideGroupsResponse,
)
from schemas.cefr import CEFRLevel


router = APIRouter(prefix="/collections", tags=["Collections"])


@router.get("", response_model=list[CollectionRead])
def get_learner_pending_collections(
    session: Annotated[Session, Depends(get_session)],
    current_learner: Annotated[
        Learner, Depends(auth_service.decode_token_to_get_learner)
    ],
    group_name: str = CEFRLevel.A1,
    limit: int = 20,
    page: int = 1,
):
    # Calculate offset: (page 1 - 1) * 20 = 0; (page 2 - 1) * 20 = 20
    offset = (page - 1) * limit
    return collection_service.get_learner_pending_collections(
        session, current_learner.id, group_name, limit, offset
    )


@router.get("/stats", response_model=list[GroupStats])
def get_group_stats(
    session: Annotated[Session, Depends(get_session)],
    current_learner: Annotated[
        Learner, Depends(auth_service.decode_token_to_get_learner)
    ],
):
    return collection_service.get_learning_collection_group_stats(
        session, current_learner.id
    )


@router.post("/overrides", response_model=OverrideGroupsResponse)
def create_group_overrides(
    session: Annotated[Session, Depends(get_session)],
    current_learner: Annotated[
        Learner, Depends(auth_service.decode_token_to_get_learner)
    ],
    payload: OverrideGroupsCreate,
):
    total_created = 0
    details = {}
    for group_name in payload.group_names:
        created_count = brick_override_service.create_overrides_for_group(
            session=session,
            learner_id=current_learner.id,
            group_name=group_name,
        )
        details[group_name] = created_count
        total_created += created_count
    return OverrideGroupsResponse(
        total_created=total_created,
        details=details,
    )
