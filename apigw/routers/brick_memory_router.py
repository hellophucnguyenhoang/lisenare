from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from database import Learner, get_session
from schemas import LearningCardStats, LearningTimeSeries
from services import auth_service, brick_memory_service

router = APIRouter(prefix="/brick-memories", tags=["Brick Memories"])


@router.get(
    "/stats",
    response_model=LearningCardStats,
    summary="Get learner statistics",
    description="Retrieve stats for a specific period. Use 'days=0' for today's data based on your timezone.",
)
def get_learning_stats(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    tz_name: Annotated[
        str,
        Query(
            description="Your IANA timezone string (e.g., 'Asia/Ho_Chi_Minh')"
        ),
    ] = "Asia/Ho_Chi_Minh",
    days: Annotated[
        int | None,
        Query(
            description="Number of days to look back calendar-based. 0 = Today (since local midnight), None = All time.",
            ge=0,
        ),
    ] = None,
):
    return brick_memory_service.get_learning_stats(
        session, learner.id, tz_name, days
    )


@router.get(
    "/stats/timeseries",
    summary="Get learner practice history",
    response_model=LearningTimeSeries,
)
def get_learning_timeseries(
    session: Annotated[Session, Depends(get_session)],
    learner: Annotated[
        Learner, Depends(auth_service.decode_token_get_learner)
    ],
    metric: Annotated[
        str,
        Query(
            description="Metric type: total_learning | reviews",
        ),
    ] = "total_learning",
    tz_name: Annotated[
        str,
        Query(
            description="Your IANA timezone string (e.g., 'Asia/Ho_Chi_Minh')"
        ),
    ] = "Asia/Ho_Chi_Minh",
    days: Annotated[
        int | None,
        Query(
            description="Number of days to look back calendar-based. 0 = Today (since local midnight), None = All time.",
            ge=0,
        ),
    ] = None,
):
    print(f"{metric=},{tz_name=},{days=}")
    result = LearningTimeSeries(
        **brick_memory_service.get_learning_timeseries(
            session,
            learner.id,
            tz_name,
            days,
            metric,
        )
    )
    result.data = brick_memory_service.fill_missing_days(
        result.data,
        days,
        fill_strategy="zero" if metric == "reviews" else "carry",
    )
    result.data = brick_memory_service.downsample_points(result.data)
    return result
