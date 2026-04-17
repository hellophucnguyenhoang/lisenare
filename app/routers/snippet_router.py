from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import get_session
from app.schemas.snippet import SnippetPage
from app.services import (
    snippet_service,
)

router = APIRouter(prefix="/snippets", tags=["Snippets"])


@router.get("/random")
def list_random_snippets(
    session: Annotated[Session, Depends(get_session)],
    page_size: int = 5,
) -> SnippetPage:
    snippets = snippet_service.get_random_snippets(session, page_size)
    snippet_page = SnippetPage(items=snippets, total=len(snippets))
    return snippet_page
