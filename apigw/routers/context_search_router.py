import time
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlmodel import Session

from config import logger
from database import Learner, get_session
from schemas import (
    BrickContextSearch,
    ContextSearchRequest,
)
from services import auth_service
from services.context_search_service import (
    initialize_embeddings,
    search_service,
)
from utils import metrics, text_utils

router = APIRouter(prefix="/context-search", tags=["Context Search"])


@router.post(
    "/init-embeddings",
    status_code=status.HTTP_201_CREATED,
    description="WARNING: This takes about 10 minutes to run.",
)
@metrics.measure_time
def init_embeddings(
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    initialize_embeddings(session, search_service)
    return Response(status_code=status.HTTP_201_CREATED)


@router.post("/bricks-search")
def search_context_bricks(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    context_search_request: ContextSearchRequest,
) -> list[BrickContextSearch]:
    start = time.time()
    search_result = search_service.search_bricks(
        session,
        text_utils.refined_spell_fix(context_search_request.query),
        learner.id,
        kind=context_search_request.kind,
        limit=context_search_request.limit,
        offset=context_search_request.offset,
    )
    end = time.time()
    logger.info(f"brick search time: {(end - start) * 1000} ms")
    return search_result
