from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlmodel import Session

from config import logger
from database import Learner, get_session
from schemas import ReviewCreate, ReviewResponse
from services import (
    auth_service,
    brick_memory_service,
    brick_review_service,
)

router = APIRouter(prefix="/brick-reviews", tags=["Brick Reviews"])


@router.post(
    "",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a review with deliberate learner rating",
)
def create_brick_review(
    session: Annotated[Session, Depends(get_session)],
    current_learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    background_tasks: BackgroundTasks,
    review_data: ReviewCreate,
) -> ReviewResponse:
    total_learner_reviews = brick_review_service.save_review(
        session=session,
        learner_id=current_learner.id,
        review_create=review_data,
    )
    logger.info(
        f"Review saved for brick ID {review_data.brick_id} "
        f"by learner ID {current_learner.id}, {total_learner_reviews=}"
    )

    # Optimize spacing intervals periodically
    if total_learner_reviews > 100:
        interval = max(200, int(total_learner_reviews**0.5 * 20))
        if total_learner_reviews % interval == 0:
            background_tasks.add_task(
                brick_memory_service.optimize_learner_scheduler,
                current_learner.id,
            )
            logger.info(
                f"Triggering background optimization for learner {current_learner.id}"
            )

    return ReviewResponse(total_reviews=total_learner_reviews)
