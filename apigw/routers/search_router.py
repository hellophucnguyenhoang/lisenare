from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlmodel import Session

from database import Learner, get_session
from schemas import (
    BrickContextSearch,
    ContextSearchRequest,
)
from services import auth_service, search_service
from utils import metrics, text_utils

router = APIRouter(prefix="/search", tags=["Brick Search"])


@router.post(
    "/init-embeddings",
    status_code=status.HTTP_201_CREATED,
    description="WARNING: This takes about 10 minutes to run.",
)
@metrics.measure_time
def init_embeddings(
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    search_service.initialize_embeddings(session)
    return Response(status_code=status.HTTP_201_CREATED)


@router.post("/bricks")
@metrics.measure_time
def search_context_bricks(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    context_search_request: ContextSearchRequest,
) -> list[BrickContextSearch]:
    search_result = search_service.search_bricks(
        session,
        text_utils.refined_spell_fix(context_search_request.query),
        learner.id,
        kind=context_search_request.kind,
        limit=context_search_request.limit,
        offset=context_search_request.offset,
        retrieval_lang=learner.retrieval_lang,
    )
    return search_result
