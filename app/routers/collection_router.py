from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.database import Learner, get_session
from app.schemas import (
    CollectionRead,
    CollectionRenameRequest,
    OverrideCreateGroupsRequest,
    OverrideCreateGroupsResponse,
    OverrideDeleteGroupsResponse,
)
from app.services import (
    auth_service,
    brick_override_service,
    collection_service,
)

router = APIRouter(prefix="/collections", tags=["Collections"])


@router.get("/pending", response_model=list[CollectionRead])
def get_pending_collections(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
):
    return collection_service.get_pending_collections(
        session,
        learner.id,
    )


@router.post("/overrides", response_model=OverrideCreateGroupsResponse)
def create_collection_overrides(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    payload: OverrideCreateGroupsRequest,
):
    print(f"{payload=}")
    total_created = 0
    details = {}
    for collection_id in payload.collection_ids:
        created_count, cloned_id = brick_override_service.create_overrides(
            session=session,
            learner_id=learner.id,
            collection_id=collection_id,
        )
        if cloned_id is not None:
            details[collection_id] = {
                "cloned_collection_id": cloned_id,
                "created_count": created_count,
            }
            total_created += created_count

    return {
        "total": total_created,
        "details": details,
    }


@router.get("/reserved-name")
def check_reserved_collection_name(
    name: str = Query(min_length=1),
) -> bool:
    return collection_service.is_reserved_collection_name(name)


@router.patch("/{collection_id}/name", response_model=CollectionRead)
def rename_collection(
    collection_id: int,
    payload: CollectionRenameRequest,
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner,
        Depends(auth_service.decode_token_get_learner),
    ],
):
    return collection_service.rename_collection(
        session=session,
        learner_id=learner.id,
        collection_id=collection_id,
        new_name=payload.name,
    )


@router.delete("/overrides")
def delete_collection_overrides(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    collection_ids: list[int] = Query(),
) -> OverrideDeleteGroupsResponse:
    total_deleted = 0
    details = {}
    for collection_id in collection_ids:
        deleted_count = brick_override_service.delete_overrides(
            session=session,
            learner_id=learner.id,
            collection_id=collection_id,
        )
        details[collection_id] = deleted_count
        total_deleted += deleted_count
    return OverrideDeleteGroupsResponse(
        total=total_deleted,
        details=details,
    )


@router.delete("/{collection_id}")
def delete_collection(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    collection_id: int,
) -> int:
    return collection_service.delete_collection(
        session, learner.id, collection_id
    )
