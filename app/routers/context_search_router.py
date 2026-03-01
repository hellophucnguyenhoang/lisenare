from fastapi import APIRouter

from app.services.context_search_service import context_search_service
from app.schemas import (
    ContextSearchRequest,
    VideoContextSearchResult,
    BrickContextSearch,
)

router = APIRouter(prefix="/context-search", tags=["Context Search"])


@router.post("/videos", response_model=list[VideoContextSearchResult])
def search_context_videos(
    context_search_request: ContextSearchRequest,
):
    return context_search_service.search_context_videos(
        context_search_request.query
    )


@router.post("/bricks", response_model=list[BrickContextSearch])
def search_context_videos(
    context_search_request: ContextSearchRequest,
):
    return context_search_service.search_context_bricks(
        context_search_request.query
    )
