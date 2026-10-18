import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlmodel import Session

from config import logger
from database import Learner, get_session
from exceptions import RequestException
from schemas import (
    AddIslandResult,
    BrickExport,
    IslandCreate,
    IslandRead,
    IslandUpdate,
)
from services import (
    auth_service,
    island_service,
)

router = APIRouter(prefix="/islands", tags=["Islands"])


@router.get("", response_model=list[IslandRead])
def get_islands(
    session: Annotated[Session, Depends(get_session)],
    creator: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
):
    results = island_service.get_islands(session, creator.id)
    return [
        IslandRead.model_validate(
            island,
            update={
                "brick_count": brick_count,
                "learned_count": learned_count,
                "tags": tags,
            },
        )
        for island, brick_count, learned_count, tags in results
    ]


@router.post(
    "", response_model=IslandRead, status_code=status.HTTP_201_CREATED
)
def create_island(
    payload: IslandCreate,
    session: Annotated[Session, Depends(get_session)],
    creator: Annotated[
        Learner,
        Depends(auth_service.decode_token_get_learner),
    ],
) -> IslandRead:
    island, tags = island_service.create_island(
        session=session,
        creator_id=creator.id,
        island_create=payload,
    )
    return IslandRead.model_validate(
        island,
        update={
            "brick_count": 0,
            "learned_count": 0,
            "tags": tags,
        },
    )


@router.patch("/{island_id}", response_model=IslandRead)
def update_island(
    island_id: int,
    payload: IslandUpdate,
    session: Annotated[Session, Depends(get_session)],
    creator: Annotated[
        Learner,
        Depends(auth_service.decode_token_get_learner),
    ],
) -> IslandRead:
    island, brick_count, learned_count, tags = island_service.update_island(
        session=session,
        creator_id=creator.id,
        island_id=island_id,
        island_update=payload,
    )
    return IslandRead.model_validate(
        island,
        update={
            "brick_count": brick_count,
            "learned_count": learned_count,
            "tags": tags,
        },
    )


@router.delete("/{island_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_island(
    session: Annotated[Session, Depends(get_session)],
    creator: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    island_id: int,
) -> Response:
    island_service.delete_island(session, creator.id, island_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{island_id}/export", response_model=list[BrickExport])
def export_island(
    island_id: int,
    session: Annotated[Session, Depends(get_session)],
    creator: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    include_memory: bool = True,
    include_review_history: bool = True,
) -> list[BrickExport]:
    return island_service.export_island(
        session=session,
        island_id=island_id,
        learner_id=creator.id,
        include_memory=include_memory,
        include_review_history=include_review_history,
    )


@router.post(
    "/{island_id}/import",
    response_model=AddIslandResult,
)
async def import_island(
    island_id: int,
    file: Annotated[UploadFile, File()],
    session: Annotated[Session, Depends(get_session)],
    creator: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
) -> AddIslandResult:
    try:
        content = json.loads(await file.read())
    except Exception as e:
        logger.warning(
            f"Failed to parse uploaded import JSON for island {island_id}: {e}"
        )
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message="Invalid JSON file",
        )

    if isinstance(content, dict) and "bricks" in content:
        content = content["bricks"]

    if not isinstance(content, list):
        logger.warning(
            f"Uploaded import JSON for island {island_id} does not contain a list of bricks"
        )
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            debug_message="JSON file must contain a list of bricks",
        )

    try:
        bricks = [BrickExport.model_validate(item) for item in content]
    except Exception as e:
        logger.warning(
            f"Validation failed for imported bricks in island {island_id}: {e}"
        )
        raise RequestException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            debug_message=f"Invalid brick data: {e}",
        )

    return island_service.import_island(
        session=session,
        island_id=island_id,
        learner_id=creator.id,
        bricks=bricks,
    )
