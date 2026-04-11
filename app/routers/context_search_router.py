import time
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import get_session
from app.schemas import (
    BrickContextSearch,
    ContextSearchRequest,
    VideoContextSearchResult,
)
from app.services.context_search_service import context_search_service

router = APIRouter(prefix="/context-search", tags=["Context Search"])


@router.post("/videos", response_model=list[VideoContextSearchResult])
def search_context_videos(
    session: Annotated[Session, Depends(get_session)],
    context_search_request: ContextSearchRequest,
):
    start = time.time()
    search_result = context_search_service.search_videos_hybrid(
        session, context_search_request.query
    )
    end = time.time()
    print(f"video search time: {(end - start) * 1000} ms")
    return search_result


@router.post("/bricks", response_model=list[BrickContextSearch])
def search_context_bricks(
    session: Annotated[Session, Depends(get_session)],
    context_search_request: ContextSearchRequest,
):
    start = time.time()
    search_result = context_search_service.search_bricks_hybrid(
        session, context_search_request.query
    )
    end = time.time()
    print(f"brick search time: {(end - start) * 1000} ms")
    return search_result
