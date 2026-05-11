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
    initialize_embeddings,
)
from utils import text_utils

router = APIRouter(prefix="/context-search", tags=["Context Search"])


@router.post(
    "/init-embeddings",
    description="WARNING: This takes about 10 minutes to run.",
)
def init_embeddings(
    session: Annotated[Session, Depends(get_session)],
) -> StatusResponse:
    start = time.time()
    initialize_embeddings(session, context_search_service)
    end = time.time()
    print(f"Initialization time: {(end - start)}s")
    return StatusResponse(
        status=StatusResponseType.SUCCESS,
        message="All embeddings are initialized successfully",
    )


@router.post("/videos-search")
def search_context_videos(
    session: Annotated[Session, Depends(get_session)],
    context_search_request: ContextSearchRequest,
) -> list[VideoContextSearchResult]:
    start = time.time()
    search_result = context_search_service.search_videos(
        session, context_search_request.query
    )
    end = time.time()
    print(f"video search time: {(end - start) * 1000} ms")
    return search_result[:30]


@router.post("/bricks-search")
def search_context_bricks(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner | None, Depends(auth_service.decode_token_get_optional_learner)
    ],
    context_search_request: ContextSearchRequest,
) -> list[BrickContextSearch]:
    learner_id = learner.id if learner else None
    start = time.time()
    search_result = context_search_service.search_bricks(
        session,
        text_utils.refined_spell_fix(context_search_request.query),
        learner_id,
    )
    end = time.time()
    print(f"brick search time: {(end - start) * 1000} ms")
    return search_result[:30]


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
    search_result = context_search_service.search_snippets(
        session, context_search_request.query
    )
    search_result = snippet_like_service.hydrate_reactions(
        session, search_result, learner_id
    )
    end = time.time()
    print(f"snippet search time: {(end - start) * 1000} ms")
    return search_result[:30]
