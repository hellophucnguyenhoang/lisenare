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
    context_search_service,
    initialize_embeddings,
)
from utils import text_utils

router = APIRouter(prefix="/context-search", tags=["Context Search"])


@router.post(
    "/init-embeddings",
    status_code=status.HTTP_201_CREATED,
    description="WARNING: This takes about 10 minutes to run.",
)
def init_embeddings(
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    start = time.time()
    initialize_embeddings(session, context_search_service)
    end = time.time()
    logger.info(f"Initialization time: {(end - start)}s")
    return Response(status_code=status.HTTP_201_CREATED)


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
    logger.info(f"brick search time: {(end - start) * 1000} ms")
    return search_result[:30]
