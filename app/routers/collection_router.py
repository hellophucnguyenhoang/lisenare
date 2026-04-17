from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import Learner, get_session
from app.schemas import (
    BrickReadSimple,
    CollectionRead,
    CollectionSort,
    CollectionStatus,
    GroupStats,
    OverrideGroupsCreate,
    OverrideGroupsResponse,
)
from app.services import (
    auth_service,
    brick_override_service,
    brick_service,
    collection_service,
)
from schemas.cefr import CEFRLevel

router = APIRouter(prefix="/collections", tags=["Collections"])


@router.get("", response_model=list[CollectionRead])
def get_collections(
    session: Annotated[Session, Depends(get_session)],
    current_learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
):
    return collection_service.get_collections(session, current_learner.id)


@router.get("/pending", response_model=list[CollectionRead])
def get_pending_collections(
    session: Annotated[Session, Depends(get_session)],
    current_learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    group_name: str = CEFRLevel.A1,
    status: CollectionStatus = CollectionStatus.ALL,
    sort_by: CollectionSort = CollectionSort.recommended,
    limit: int = 20,
    page: int = 1,
):
    # Calculate offset: (page 1 - 1) * 20 = 0; (page 2 - 1) * 20 = 20
    offset = (page - 1) * limit
    return collection_service.get_pending_collections(
        session, current_learner.id, group_name, status, sort_by, limit, offset
    )


@router.get("/pending-groups")
def get_pending_groups(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
):
    return collection_service.get_pending_groups(session, learner.id)


@router.get("/pending-bricks", response_model=list[BrickReadSimple])
def get_pending_bricks_collection(
    session: Annotated[Session, Depends(get_session)],
    current_learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    collection_id: int,
):
    return brick_service.get_pending_bricks(
        session, current_learner.id, collection_id
    )


@router.get("/stats", response_model=list[GroupStats])
def get_pending_collection_group_stats(
    session: Annotated[Session, Depends(get_session)],
    current_learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
):
    return collection_service.get_pending_collection_group_stats(
        session, current_learner.id
    )


@router.post("/overrides")
def create_group_overrides(
    session: Annotated[Session, Depends(get_session)],
    current_learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    payload: OverrideGroupsCreate,
) -> OverrideGroupsResponse:
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
