from app.services.context_search_service import context_search_service
from app.schemas import ContextSearchRequest, ContextSearchResult
from fastapi import APIRouter

router = APIRouter(prefix="/context-search", tags=["Context Search"])

@router.post("", response_model=list[ContextSearchResult])
def search_context(
    context_search_request: ContextSearchRequest,
):
    return context_search_service.search_context(context_search_request.query)
