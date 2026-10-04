import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlmodel import Session

from database import Learner, get_session
from exceptions import RequestException
from schemas import (
    AddCollectionResult,
    BrickExport,
    CollectionCreate,
    CollectionRead,
    CollectionUpdate,
)
from services import (
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


@router.post(
    "", response_model=CollectionRead, status_code=status.HTTP_201_CREATED
)
def create_collection(
    payload: CollectionCreate,
    session: Annotated[Session, Depends(get_session)],
    creator: Annotated[
        Learner,
        Depends(auth_service.decode_token_get_learner),
    ],
) -> CollectionRead:
    collection, tags = collection_service.create_collection(
        session=session,
        creator_id=creator.id,
        collection_create=payload,
    )
    return CollectionRead.model_validate(
        collection,
        update={
            "brick_count": 0,
            "learned_count": 0,
            "tags": tags,
        },
    )


@router.patch("/{collection_id}", response_model=CollectionRead)
def update_collection(
    collection_id: int,
    payload: CollectionUpdate,
    session: Annotated[Session, Depends(get_session)],
    creator: Annotated[
        Learner,
        Depends(auth_service.decode_token_get_learner),
    ],
) -> CollectionRead:
    collection, brick_count, learned_count, tags = (
        collection_service.update_collection(
            session=session,
            creator_id=creator.id,
            collection_id=collection_id,
            collection_update=payload,
        )
    )
    return CollectionRead.model_validate(
        collection,
        update={
            "brick_count": brick_count,
            "learned_count": learned_count,
            "tags": tags,
        },
    )


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(
    session: Annotated[Session, Depends(get_session)],
    creator: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    collection_id: int,
) -> Response:
    collection_service.delete_collection(session, creator.id, collection_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{collection_id}/export", response_model=list[BrickExport])
def export_collection(
    collection_id: int,
    session: Annotated[Session, Depends(get_session)],
    creator: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
) -> list[BrickExport]:
    return collection_service.export_collection(
        session=session,
        collection_id=collection_id,
        learner_id=creator.id,
    )


@router.post(
    "/{collection_id}/import",
    response_model=AddCollectionResult,
)
async def import_collection(
    collection_id: int,
    file: Annotated[UploadFile, File()],
    session: Annotated[Session, Depends(get_session)],
    creator: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
) -> AddCollectionResult:
    try:
        content = json.loads(await file.read())
    except Exception:
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message="Invalid JSON file",
        )

    if isinstance(content, dict) and "bricks" in content:
        content = content["bricks"]

    if not isinstance(content, list):
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message="JSON file must contain a list of bricks",
        )

    try:
        bricks = [BrickExport.model_validate(item) for item in content]
    except Exception as e:
        raise RequestException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            debug_message=f"Invalid brick data: {e}",
        )

    return collection_service.import_collection(
        session=session,
        collection_id=collection_id,
        learner_id=creator.id,
        bricks=bricks,
    )
