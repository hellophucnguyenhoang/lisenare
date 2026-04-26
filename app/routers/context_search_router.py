import time
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import Learner, get_session
from app.schemas import (
    BrickContextSearch,
    ContextSearchRequest,
    SnippetRead,
    StatusResponse,
    StatusResponseType,
    VideoContextSearchResult,
)
from app.services import auth_service, snippet_like_service
from app.services.context_search_service import (
    context_search_service,
    search_snippets_literal,
)

router = APIRouter(prefix="/context-search", tags=["Context Search"])


@router.post("/snippet/{snippet_id}")
def upsert_context_snippet(
    session: Annotated[Session, Depends(get_session)], snippet_id: int
) -> StatusResponse:
    context_search_service.upsert_context_snippet(session, snippet_id)
    return StatusResponse(
        status=StatusResponseType.SUCCESS,
        message=f"Snippet {snippet_id} upserted successfully",
    )


@router.post("/brick/{brick_id}")
def upsert_context_brick(
    session: Annotated[Session, Depends(get_session)], brick_id: int
) -> StatusResponse:
    context_search_service.upsert_context_brick(session, brick_id)
    return StatusResponse(
        status=StatusResponseType.SUCCESS,
        message=f"Brick {brick_id} upserted successfully",
    )


@router.post(
    "/all-snippets", description="WARNING: This take a long time to run"
)
def upsert_context_all_snippets(
    session: Annotated[Session, Depends(get_session)],
) -> StatusResponse:
    context_search_service.upsert_context_all_snippets(session)
    return StatusResponse(
        status=StatusResponseType.SUCCESS,
        message="Snippets upserted successfully",
    )


@router.post(
    "/all-bricks", description="WARNING: This take a long time to run"
)
def upsert_context_all_bricks(
    session: Annotated[Session, Depends(get_session)],
) -> StatusResponse:
    context_search_service.upsert_context_all_bricks(session)
    return StatusResponse(
        status=StatusResponseType.SUCCESS,
        message="Bricks upserted successfully",
    )


@router.post("/snippets-search")
def search_context_snippets(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner | None, Depends(auth_service.decode_token_get_optional_learner)
    ],
    context_search_request: ContextSearchRequest,
) -> list[SnippetRead]:
    learner_id = learner.id if learner else None
    start = time.time()
    search_result = search_snippets_literal(
        session, context_search_request.query
    )
    search_result = snippet_like_service.apply_like_state_to_reads(
        session, search_result, learner_id
    )
    end = time.time()
    print(f"snippet search time: {(end - start) * 1000} ms")
    return search_result[:30]


@router.post("/videos-search")
def search_context_videos(
    session: Annotated[Session, Depends(get_session)],
    context_search_request: ContextSearchRequest,
) -> list[VideoContextSearchResult]:
    start = time.time()
    search_result = context_search_service.search_videos_hybrid(
        session, context_search_request.query
    )
    end = time.time()
    print(f"video search time: {(end - start) * 1000} ms")
    return search_result


@router.post("/bricks-search")
def search_context_bricks(
    session: Annotated[Session, Depends(get_session)],
    context_search_request: ContextSearchRequest,
) -> list[BrickContextSearch]:
    start = time.time()
    search_result = context_search_service.search_bricks_hybrid(
        session, context_search_request.query
    )
    end = time.time()
    print(f"brick search time: {(end - start) * 1000} ms")
    return search_result
