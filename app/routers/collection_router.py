from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlmodel import Session

from app.database import Learner, get_session
from app.schemas import (
    CollectionRead,
    CollectionRenameRequest,
)
from app.services import (
    auth_service,
    collection_service,
)

router = APIRouter(prefix="/collections", tags=["Collections"])


@router.get("", response_model=list[CollectionRead])
def get_collections(
    session: Annotated[Session, Depends(get_session)],
    creator: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
):
    results = collection_service.get_collections(session, creator.id)
    return [
        CollectionRead.model_validate(
            collection,
            update={
                "brick_count": brick_count,
                "learned_count": learned_count,
                "tags": tags,
            },
        )
        for collection, brick_count, learned_count, tags in results
    ]


@router.patch("/{collection_id}/name", response_model=CollectionRead)
def rename_collection(
    collection_id: int,
    payload: CollectionRenameRequest,
    session: Annotated[Session, Depends(get_session)],
    creator: Annotated[
        Learner,
        Depends(auth_service.decode_token_get_learner),
    ],
):
    return collection_service.rename_collection(
        session=session,
        creator_id=creator.id,
        collection_id=collection_id,
        new_name=payload.new_name,
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(
    session: Annotated[Session, Depends(get_session)],
    creator: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    collection_id: int,
) -> Response:
    collection_service.delete_collection(session, creator.id, collection_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
